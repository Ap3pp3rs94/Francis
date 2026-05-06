[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(1, 50)]
  [int]$Limit = 5
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

function Find-Criterion {
  param(
    [AllowNull()]
    [object]$Criteria,
    [string]$CriterionId
  )

  foreach ($Criterion in @($Criteria)) {
    if ([string](Get-PropertyValue -Payload $Criterion -Name 'id' -Default '') -eq $CriterionId) {
      return $Criterion
    }
  }
  return $null
}

function Invoke-LensStatusReadback {
  param([int]$StatusLimit)

  $Python = Get-Command python -ErrorAction SilentlyContinue
  if ($null -eq $Python) {
    throw 'Python is required to read lens_status.'
  }

  $PreviousPythonPath = $env:PYTHONPATH
  $SrcPath = Join-Path $RepoRoot 'src'
  if ([string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
    $env:PYTHONPATH = $SrcPath
  } elseif ($PreviousPythonPath -notlike "*$SrcPath*") {
    $env:PYTHONPATH = "$SrcPath;$PreviousPythonPath"
  }

$PythonCode = @"
import json
from francis.lens.status import lens_status
print(json.dumps(lens_status(limit=$StatusLimit)))
"@

  try {
    $Output = & $Python.Source -c $PythonCode 2>&1
    $ExitCode = $LASTEXITCODE
  } finally {
    $env:PYTHONPATH = $PreviousPythonPath
  }

  $Text = ($Output | ForEach-Object { [string]$_ }) -join "`n"
  if ($ExitCode -ne 0) {
    throw "lens_status readback failed with exit code $ExitCode. $Text"
  }

  return $Text | ConvertFrom-Json -ErrorAction Stop
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$StatusReadback = Invoke-LensStatusReadback -StatusLimit $Limit
$Stage6Readiness = Get-PropertyValue -Payload $StatusReadback -Name 'stage6_readiness'
$ClosureReadback = Get-PropertyValue -Payload $Stage6Readiness -Name 'closure_readback'
$Criteria = Get-PropertyValue -Payload $ClosureReadback -Name 'criteria' -Default @()
$BlockedCriteria = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ClosureReadback -Name 'blocked_criteria')
$ReadyCriteria = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ClosureReadback -Name 'ready_criteria')
$StageNextGap = [string](Get-PropertyValue -Payload $ClosureReadback -Name 'next_smallest_truthful_gap' -Default '')

$FirstBlockedCriterionId = ''
if (@($BlockedCriteria).Count -gt 0) {
  $FirstBlockedCriterionId = [string]$BlockedCriteria[0]
}
$FirstBlockedCriterion = Find-Criterion -Criteria $Criteria -CriterionId $FirstBlockedCriterionId
$CriterionHandoff = Get-PropertyValue -Payload $FirstBlockedCriterion -Name 'handoff' -Default ([ordered]@{})
$FirstBlockerFamily = [string](Get-PropertyValue -Payload $CriterionHandoff -Name 'first_blocker_family' -Default '')
$FirstBlockerFamilyHandoff = Get-PropertyValue -Payload $CriterionHandoff -Name 'first_blocker_family_handoff' -Default ([ordered]@{})
$FirstFamilyCompletionAuditHandoff = Get-PropertyValue -Payload $CriterionHandoff -Name 'first_blocker_family_completion_audit_handoff' -Default ([ordered]@{})
$FamilyChainCompletionAuditHandoff = Get-PropertyValue -Payload $CriterionHandoff -Name 'summon_anywhere_family_chain_completion_audit_handoff' -Default ([ordered]@{})

$CriterionNextGap = [string](Get-PropertyValue -Payload $FirstBlockedCriterion -Name 'next_smallest_truthful_gap' -Default '')
$FamilyNextGap = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'next_smallest_truthful_gap' -Default '')
$RecommendedNextSlice = $FamilyNextGap
if ([string]::IsNullOrWhiteSpace($RecommendedNextSlice)) {
  $RecommendedNextSlice = $CriterionNextGap
}
if ([string]::IsNullOrWhiteSpace($RecommendedNextSlice)) {
  $RecommendedNextSlice = $StageNextGap
}

$RecommendedProofScript = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'proof_script' -Default '')
$RecommendedRoute = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'route' -Default '')
$RecommendedReadinessRoute = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'readiness_route' -Default '')
$AuthorityRequired = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'authority_required' -Default '')

$ClosureObserved = (
  [string](Get-PropertyValue -Payload $ClosureReadback -Name 'kind' -Default '') -eq 'lens.stage6.closure_readback' -and
  [string](Get-PropertyValue -Payload $ClosureReadback -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $ClosureReadback -Name 'ready_to_close' -Default $true)
)
$StageBoundaryObserved = (
  [string](Get-PropertyValue -Payload $Stage6Readiness -Name 'stage' -Default '') -eq 'Stage 6 / Lens MVP' -and
  [string](Get-PropertyValue -Payload $Stage6Readiness -Name 'stage_state' -Default '') -eq 'active'
)
$FirstBlockedCriterionObserved = (
  $FirstBlockedCriterionId -eq 'summon_anywhere' -and
  [string](Get-PropertyValue -Payload $FirstBlockedCriterion -Name 'status' -Default '') -eq 'blocked'
)
$FirstFamilyHandoffObserved = (
  $FirstBlockerFamily -eq 'resident_host' -and
  [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'status' -Default '') -eq 'blocked' -and
  -not [string]::IsNullOrWhiteSpace($FamilyNextGap) -and
  -not [string]::IsNullOrWhiteSpace($RecommendedProofScript) -and
  -not [string]::IsNullOrWhiteSpace($RecommendedRoute)
)
$CompletionAuditHandoffObserved = (
  [string](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'authority_required' -Default '') -eq 'process_supervision_authority' -and
  [bool](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'diagnostic_only' -Default $false)
)
$FamilyChainHandoffObserved = (
  [string](Get-PropertyValue -Payload $FamilyChainCompletionAuditHandoff -Name 'authority_required' -Default '') -eq 'resident_runtime_execution_authority' -and
  [bool](Get-PropertyValue -Payload $FamilyChainCompletionAuditHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $FamilyChainCompletionAuditHandoff -Name 'diagnostic_only' -Default $false)
)
$SideEffectsDenied = (
  -not [bool](Get-PropertyValue -Payload $CriterionHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $CriterionHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $FamilyChainCompletionAuditHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $FamilyChainCompletionAuditHandoff -Name 'would_mutate' -Default $false)
)

$Checks = @(
  New-Check -Id 'closure_readback' -Status 'blocked_closure_readback_observed' -Passed $ClosureObserved -Evidence '/lens/status stage6_readiness.closure_readback' -Reason 'Stage 6 closure must remain blocked before transition.'
  New-Check -Id 'stage_boundary' -Status 'stage6_active' -Passed $StageBoundaryObserved -Evidence '/lens/status stage6_readiness' -Reason 'The next handoff only applies while Stage 6 is active.'
  New-Check -Id 'first_blocked_criterion' -Status 'summon_anywhere_blocked' -Passed $FirstBlockedCriterionObserved -Evidence 'closure_readback.blocked_criteria[0]' -Reason 'Summon-anywhere is still the first blocked acceptance criterion.'
  New-Check -Id 'first_blocker_family_handoff' -Status 'resident_host_handoff_ready' -Passed $FirstFamilyHandoffObserved -Evidence 'summon_anywhere.handoff.first_blocker_family_handoff' -Reason 'The next concrete handoff points at the resident host runtime boundary.'
  New-Check -Id 'completion_audit_handoff' -Status 'process_supervision_audit_handoff_ready' -Passed $CompletionAuditHandoffObserved -Evidence 'summon_anywhere.handoff.first_blocker_family_completion_audit_handoff' -Reason 'The process-supervision handoff is present but diagnostic-only.'
  New-Check -Id 'family_chain_handoff' -Status 'summon_family_chain_handoff_ready' -Passed $FamilyChainHandoffObserved -Evidence 'summon_anywhere.handoff.summon_anywhere_family_chain_completion_audit_handoff' -Reason 'The summon blocker family chain can still be consumed by audit.'
  New-Check -Id 'side_effects_denied' -Status 'readback_only' -Passed $SideEffectsDenied -Evidence 'handoff governance flags' -Reason 'The handoff script must not grant or imply execution authority.'
)
$Ok = -not @($Checks | Where-Object { -not [bool](Get-PropertyValue -Payload $_ -Name 'passed' -Default $false) })

$Payload = [ordered]@{
  kind = 'lens.stage6.next_handoff.proof'
  status = if ($Ok) { 'proof_passed' } else { 'blocked' }
  ok = $Ok
  mode = $Mode.ToLowerInvariant()
  stage = [string](Get-PropertyValue -Payload $Stage6Readiness -Name 'stage' -Default '')
  stage_state = [string](Get-PropertyValue -Payload $Stage6Readiness -Name 'stage_state' -Default '')
  ready_to_close = [bool](Get-PropertyValue -Payload $ClosureReadback -Name 'ready_to_close' -Default $false)
  stage_next_smallest_truthful_gap = $StageNextGap
  next_smallest_truthful_gap = $RecommendedNextSlice
  acceptance_criterion = $FirstBlockedCriterionId
  acceptance_criterion_status = [string](Get-PropertyValue -Payload $FirstBlockedCriterion -Name 'status' -Default '')
  criterion_next_smallest_truthful_gap = $CriterionNextGap
  first_blocker_family = $FirstBlockerFamily
  first_blocker_family_next_smallest_truthful_gap = $FamilyNextGap
  recommended_next_slice = $RecommendedNextSlice
  recommended_proof_script = $RecommendedProofScript
  recommended_route = $RecommendedRoute
  recommended_readiness_route = $RecommendedReadinessRoute
  authority_required = $AuthorityRequired
  blocked_criteria = $BlockedCriteria
  ready_criteria = $ReadyCriteria
  first_blocker_family_handoff = $FirstBlockerFamilyHandoff
  first_blocker_family_completion_audit_handoff = $FirstFamilyCompletionAuditHandoff
  summon_anywhere_family_chain_completion_audit_handoff = $FamilyChainCompletionAuditHandoff
  checks = $Checks
  governance = [ordered]@{
    diagnostic_only = $true
    read_only_contract = $true
    uses_lens_status_readback = $true
    proof_script = 'scripts/lens-stage6-next-handoff.ps1 -Mode Status'
    would_execute = $false
    would_mutate = $false
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    approval_request_write = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
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
}

$Payload | ConvertTo-Json -Depth 24
if ($Ok) {
  exit 0
}
exit 1
