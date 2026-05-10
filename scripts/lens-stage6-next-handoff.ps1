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
$ResidentHostReadback = Get-PropertyValue -Payload $StatusReadback -Name 'resident_host' -Default ([ordered]@{})
$FreshResidentRuntimeCandidateSupervised = [bool](
  Get-PropertyValue -Payload $ResidentHostReadback -Name 'fresh_resident_runtime_candidate_supervised' -Default $false
)
$ResidentRuntimeCandidateSupervised = [bool](
  Get-PropertyValue -Payload $ResidentHostReadback -Name 'resident_runtime_candidate_supervised' -Default $false
)
$SupervisorFreshnessStatus = [string](
  Get-PropertyValue -Payload $ResidentHostReadback -Name 'supervisor_freshness_status' -Default ''
)
$PersistentSupervisionPlanReadback = Get-PropertyValue -Payload $ResidentHostReadback -Name 'persistent_supervision_plan' -Default ([ordered]@{})
$PersistentSupervisionEnablementReadback = Get-PropertyValue -Payload $ResidentHostReadback -Name 'persistent_supervision_enablement' -Default ([ordered]@{})
$PersistentSupervisionMissingRequiredBeforeEnable = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $PersistentSupervisionPlanReadback -Name 'missing_required_before_enable'
)
$PersistentSupervisionEnablementMissingRequiredBeforeEnable = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $PersistentSupervisionEnablementReadback -Name 'missing_required_before_enable'
)
$PersistentSupervisionFirstMissingRequiredBeforeEnable = [string](
  Get-PropertyValue -Payload $PersistentSupervisionPlanReadback -Name 'first_missing_required_before_enable' -Default ''
)
$PersistentSupervisionFirstMissingRequirementHandoff = Get-PropertyValue -Payload $PersistentSupervisionPlanReadback -Name 'first_missing_requirement_handoff' -Default ([ordered]@{})
$ActivationStateReadback = Get-PropertyValue -Payload $ResidentHostReadback -Name 'activation_state' -Default ([ordered]@{})
$ActivationExecutionHandoff = Get-PropertyValue -Payload $ActivationStateReadback -Name 'latest_execution_handoff' -Default ([ordered]@{})
$ActivationExecutionHandoffReady = (
  [bool](Get-PropertyValue -Payload $ActivationStateReadback -Name 'latest_execution_handoff_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'id' -Default '') -eq 'resident_host_process' -and
  [bool](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'would_mutate' -Default $false)
)
$PersistentSupervisionFirstMissingRequirementHandoffReady = (
  -not [string]::IsNullOrWhiteSpace($PersistentSupervisionFirstMissingRequiredBeforeEnable) -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'id' -Default '') -eq $PersistentSupervisionFirstMissingRequiredBeforeEnable -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'would_mutate' -Default $false)
)
$PersistentSupervisionRequiredPrerequisitesObserved = (
  @($PersistentSupervisionMissingRequiredBeforeEnable).Count -gt 0 -and
  @($PersistentSupervisionEnablementMissingRequiredBeforeEnable).Count -gt 0 -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionPlanReadback -Name 'required_before_enable_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementReadback -Name 'required_before_enable_ready' -Default $true)
)
$PersistentSupervisionRequiredPrerequisitesHandoff = [ordered]@{}
if ($PersistentSupervisionRequiredPrerequisitesObserved) {
  $PersistentSupervisionRequiredPrerequisitesHandoff = [ordered]@{
    next_step = 'resolve_persistent_supervision_required_prerequisites_before_enablement'
    proof_script = 'scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status'
    route = '/lens/host/persistent-supervision'
    readiness_route = '/lens/host/persistent-supervision/enablement'
    next_smallest_truthful_gap = 'persistent_supervision_required_prerequisites_missing'
    missing_required_before_enable = [string[]]@($PersistentSupervisionMissingRequiredBeforeEnable)
    first_missing_required_before_enable = $PersistentSupervisionFirstMissingRequiredBeforeEnable
    first_missing_requirement_handoff = $PersistentSupervisionFirstMissingRequirementHandoff
    acceptance_criterion = 'system_resident_presence'
    authority_required = 'resident_host_process_tray_hotkey_overlay_and_summon_prerequisites'
    authority_granted = $false
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
  }
}

$FirstMissingResidentCandidateSupervised = [bool](
  Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'resident_runtime_candidate_supervised' -Default $false
)
$SupervisionExecutionReceiptObserved = [bool](
  Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'supervision_execution_receipt_observed' -Default $false
)
$SupervisionExecutionReceiptId = [string](
  Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'supervision_execution_receipt_id' -Default ''
)
$CandidateObservedByFreshSupervisor = (
  $FreshResidentRuntimeCandidateSupervised -and
  $ResidentRuntimeCandidateSupervised -and
  $SupervisorFreshnessStatus -eq 'fresh'
)
$CandidateObservedByDurableReceipt = (
  $SupervisionExecutionReceiptObserved -and
  $FirstMissingResidentCandidateSupervised -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'supervision_execution_next_smallest_truthful_gap' -Default '') -eq 'resident_supervision_not_persistent'
)
$ResidentRuntimeCandidateHandoff = [ordered]@{}
$ResidentRuntimeCandidateHandoffObserved = (
  $PersistentSupervisionFirstMissingRequirementHandoffReady -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'id' -Default '') -eq 'resident_host_process' -and
  @(
    'resident_host_process_not_supervised',
    'resident_supervision_not_persistent'
  ) -contains [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'next_smallest_truthful_gap' -Default '') -and
  ($CandidateObservedByFreshSupervisor -or $CandidateObservedByDurableReceipt)
)
if ($ResidentRuntimeCandidateHandoffObserved) {
  $ResidentRuntimeCandidateHandoff = [ordered]@{
    id = 'resident_runtime_candidate'
    status = 'observed_not_persistent'
    previous_next_smallest_truthful_gap = 'resident_host_process_not_supervised'
    next_smallest_truthful_gap = 'resident_supervision_not_persistent'
    recommended_next_slice = 'resolve_resident_supervision_persistence_before_persistent_supervision_enablement'
    proof_script = 'scripts/lens-resident-supervision-persistence-boundary-proof.ps1 -Mode Status'
    route = '/lens/host'
    readiness_route = '/lens/host/runtime-loop/readiness'
    source = $(if ($CandidateObservedByDurableReceipt) { '/lens/status resident_host.persistent_supervision_plan.first_missing_requirement_handoff.supervision_execution_receipt_observed' } else { '/lens/status resident_host.fresh_resident_runtime_candidate_supervised' })
    receipt_id = $SupervisionExecutionReceiptId
    candidate_observed_by_fresh_supervisor = $CandidateObservedByFreshSupervisor
    candidate_observed_by_supervision_execution_receipt = $CandidateObservedByDurableReceipt
    blocked_reason = 'resident_supervision_not_persistent'
    acceptance_criterion = 'system_resident_presence'
    authority_required = 'persistent_process_supervision_authority'
    previous_diagnostic_proof_observed = $true
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
  }
}

$CriterionNextGap = [string](Get-PropertyValue -Payload $FirstBlockedCriterion -Name 'next_smallest_truthful_gap' -Default '')
$FamilyNextGap = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'next_smallest_truthful_gap' -Default '')
$FamilyProofScript = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'proof_script' -Default '')
$RecommendedNextGap = $FamilyNextGap
if ([string]::IsNullOrWhiteSpace($RecommendedNextGap)) {
  $RecommendedNextGap = $CriterionNextGap
}
if ([string]::IsNullOrWhiteSpace($RecommendedNextGap)) {
  $RecommendedNextGap = $StageNextGap
}

$RecommendedNextSlice = $RecommendedNextGap
$RecommendedProofScript = $FamilyProofScript
$RecommendedRoute = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'route' -Default '')
$RecommendedReadinessRoute = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'readiness_route' -Default '')
$AuthorityRequired = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'authority_required' -Default '')
$RecommendedHandoffSource = 'first_blocker_family_handoff'

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
$CompletionAuditProofScript = [string](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'proof_script' -Default '')
$CompletionAuditNextGap = [string](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'next_smallest_truthful_gap' -Default '')
$CompletionAuditNextStep = [string](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'next_step' -Default '')
if (
  $CompletionAuditHandoffObserved -and
  -not [string]::IsNullOrWhiteSpace($CompletionAuditProofScript) -and
  -not [string]::IsNullOrWhiteSpace($CompletionAuditNextGap)
) {
  $RecommendedHandoffSource = 'first_blocker_family_completion_audit_handoff'
  $RecommendedNextGap = $CompletionAuditNextGap
  $RecommendedNextSlice = $CompletionAuditNextStep
  if ([string]::IsNullOrWhiteSpace($RecommendedNextSlice)) {
    $RecommendedNextSlice = $CompletionAuditNextGap
  }
  $RecommendedProofScript = $CompletionAuditProofScript
  $AuthorityRequired = [string](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'authority_required' -Default '')
}
if ($PersistentSupervisionRequiredPrerequisitesObserved) {
  $RecommendedHandoffSource = 'persistent_supervision_required_prerequisites_handoff'
  $RecommendedNextGap = 'persistent_supervision_required_prerequisites_missing'
  $RecommendedNextSlice = 'resolve_persistent_supervision_required_prerequisites_before_enablement'
  $RecommendedProofScript = 'scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status'
  $RecommendedRoute = '/lens/host/persistent-supervision'
  $RecommendedReadinessRoute = '/lens/host/persistent-supervision/enablement'
  $AuthorityRequired = 'resident_host_process_tray_hotkey_overlay_and_summon_prerequisites'
}
if ($PersistentSupervisionFirstMissingRequirementHandoffReady) {
  $FirstMissingNextGap = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'next_smallest_truthful_gap' -Default '')
  $FirstMissingNextSlice = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'next_step' -Default '')
  $FirstMissingProofScript = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'proof_script' -Default '')
  $FirstMissingRoute = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'route' -Default '')
  $FirstMissingReadinessRoute = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'readiness_route' -Default '')
  $FirstMissingAuthorityRequired = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'authority_required' -Default '')

  if (-not [string]::IsNullOrWhiteSpace($FirstMissingNextGap)) {
    $RecommendedHandoffSource = 'persistent_supervision_first_missing_requirement_handoff'
    $RecommendedNextGap = $FirstMissingNextGap
  }
  if (-not [string]::IsNullOrWhiteSpace($FirstMissingNextSlice)) {
    $RecommendedNextSlice = $FirstMissingNextSlice
  }
  if (-not [string]::IsNullOrWhiteSpace($FirstMissingProofScript)) {
    $RecommendedProofScript = $FirstMissingProofScript
  }
  if (-not [string]::IsNullOrWhiteSpace($FirstMissingRoute)) {
    $RecommendedRoute = $FirstMissingRoute
  }
  if (-not [string]::IsNullOrWhiteSpace($FirstMissingReadinessRoute)) {
    $RecommendedReadinessRoute = $FirstMissingReadinessRoute
  }
  if (-not [string]::IsNullOrWhiteSpace($FirstMissingAuthorityRequired)) {
    $AuthorityRequired = $FirstMissingAuthorityRequired
  }
}
if ($ActivationExecutionHandoffReady) {
  $ActivationExecutionNextGap = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'next_smallest_truthful_gap' -Default '')
  $ActivationExecutionNextSlice = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'next_step' -Default '')
  $ActivationExecutionProofScript = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'proof_script' -Default '')
  $ActivationExecutionRoute = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'route' -Default '')
  $ActivationExecutionReadinessRoute = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'readiness_route' -Default '')
  $ActivationExecutionAuthorityRequired = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'authority_required' -Default '')

  if (-not [string]::IsNullOrWhiteSpace($ActivationExecutionNextGap)) {
    $RecommendedHandoffSource = 'activation_execution_handoff'
    $RecommendedNextGap = $ActivationExecutionNextGap
  }
  if (-not [string]::IsNullOrWhiteSpace($ActivationExecutionNextSlice)) {
    $RecommendedNextSlice = $ActivationExecutionNextSlice
  }
  if (-not [string]::IsNullOrWhiteSpace($ActivationExecutionProofScript)) {
    $RecommendedProofScript = $ActivationExecutionProofScript
  }
  if (-not [string]::IsNullOrWhiteSpace($ActivationExecutionRoute)) {
    $RecommendedRoute = $ActivationExecutionRoute
  }
  if (-not [string]::IsNullOrWhiteSpace($ActivationExecutionReadinessRoute)) {
    $RecommendedReadinessRoute = $ActivationExecutionReadinessRoute
  }
  if (-not [string]::IsNullOrWhiteSpace($ActivationExecutionAuthorityRequired)) {
    $AuthorityRequired = $ActivationExecutionAuthorityRequired
  }
}
if ($ResidentRuntimeCandidateHandoffObserved) {
  $RecommendedHandoffSource = 'resident_runtime_candidate_handoff'
  $RecommendedNextGap = 'resident_supervision_not_persistent'
  $RecommendedNextSlice = [string](Get-PropertyValue -Payload $ResidentRuntimeCandidateHandoff -Name 'recommended_next_slice' -Default '')
  $RecommendedProofScript = [string](Get-PropertyValue -Payload $ResidentRuntimeCandidateHandoff -Name 'proof_script' -Default '')
  $RecommendedRoute = [string](Get-PropertyValue -Payload $ResidentRuntimeCandidateHandoff -Name 'route' -Default '')
  $RecommendedReadinessRoute = [string](Get-PropertyValue -Payload $ResidentRuntimeCandidateHandoff -Name 'readiness_route' -Default '')
  $AuthorityRequired = [string](Get-PropertyValue -Payload $ResidentRuntimeCandidateHandoff -Name 'authority_required' -Default '')
}
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
  -not [bool](Get-PropertyValue -Payload $FamilyChainCompletionAuditHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'would_mutate' -Default $false)
)

$Checks = @(
  New-Check -Id 'closure_readback' -Status 'blocked_closure_readback_observed' -Passed $ClosureObserved -Evidence '/lens/status stage6_readiness.closure_readback' -Reason 'Stage 6 closure must remain blocked before transition.'
  New-Check -Id 'stage_boundary' -Status 'stage6_active' -Passed $StageBoundaryObserved -Evidence '/lens/status stage6_readiness' -Reason 'The next handoff only applies while Stage 6 is active.'
  New-Check -Id 'first_blocked_criterion' -Status 'summon_anywhere_blocked' -Passed $FirstBlockedCriterionObserved -Evidence 'closure_readback.blocked_criteria[0]' -Reason 'Summon-anywhere is still the first blocked acceptance criterion.'
  New-Check -Id 'first_blocker_family_handoff' -Status 'resident_host_handoff_ready' -Passed $FirstFamilyHandoffObserved -Evidence 'summon_anywhere.handoff.first_blocker_family_handoff' -Reason 'The next concrete handoff points at the resident host runtime boundary.'
  New-Check -Id 'completion_audit_handoff' -Status 'process_supervision_audit_handoff_ready' -Passed $CompletionAuditHandoffObserved -Evidence 'summon_anywhere.handoff.first_blocker_family_completion_audit_handoff' -Reason 'The process-supervision handoff is present but diagnostic-only.'
  New-Check -Id 'family_chain_handoff' -Status 'summon_family_chain_handoff_ready' -Passed $FamilyChainHandoffObserved -Evidence 'summon_anywhere.handoff.summon_anywhere_family_chain_completion_audit_handoff' -Reason 'The summon blocker family chain can still be consumed by audit.'
  New-Check -Id 'persistent_supervision_required_prerequisites' -Status 'required_prerequisites_handoff_ready' -Passed $PersistentSupervisionRequiredPrerequisitesObserved -Evidence '/lens/status resident_host.persistent_supervision_plan missing_required_before_enable' -Reason 'The latest Stage 6 handoff must preserve the full persistent-supervision prerequisite map after the audit chain consumes the older resident-host proofs.'
  New-Check -Id 'persistent_supervision_first_missing_requirement' -Status $(if ($PersistentSupervisionFirstMissingRequirementHandoffReady) { 'first_missing_requirement_handoff_ready' } else { 'missing_or_unexpected' }) -Passed $PersistentSupervisionFirstMissingRequirementHandoffReady -Evidence '/lens/status resident_host.persistent_supervision_plan first_missing_requirement_handoff' -Reason 'The persistent-supervision prerequisite gap must name the first concrete missing prerequisite before the next slice.'
  New-Check -Id 'activation_execution_handoff' -Status $(if ($ActivationExecutionHandoffReady) { 'activation_execution_handoff_ready' } else { 'not_observed' }) -Passed $true -Evidence '/lens/status resident_host.activation_state latest_execution_handoff' -Reason 'When a bounded activation execution receipt exists, the handoff can point directly at process-supervision proof without claiming resident host status.'
  New-Check -Id 'resident_runtime_candidate_handoff' -Status $(if ($ResidentRuntimeCandidateHandoffObserved -and $CandidateObservedByDurableReceipt) { 'receipt_candidate_handoff_ready' } elseif ($ResidentRuntimeCandidateHandoffObserved) { 'fresh_candidate_handoff_ready' } else { 'not_observed' }) -Passed $true -Evidence '/lens/status resident_host resident candidate readback' -Reason 'When a fresh or receipt-backed supervised resident candidate is present, the handoff can point at persistence; otherwise it remains on the first missing resident-host prerequisite.'
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
  next_smallest_truthful_gap = $RecommendedNextGap
  acceptance_criterion = $FirstBlockedCriterionId
  acceptance_criterion_status = [string](Get-PropertyValue -Payload $FirstBlockedCriterion -Name 'status' -Default '')
  criterion_next_smallest_truthful_gap = $CriterionNextGap
  first_blocker_family = $FirstBlockerFamily
  first_blocker_family_next_smallest_truthful_gap = $FamilyNextGap
  recommended_next_slice = $RecommendedNextSlice
  recommended_handoff_source = $RecommendedHandoffSource
  recommended_proof_script = $RecommendedProofScript
  recommended_route = $RecommendedRoute
  recommended_readiness_route = $RecommendedReadinessRoute
  authority_required = $AuthorityRequired
  blocked_criteria = $BlockedCriteria
  ready_criteria = $ReadyCriteria
  first_blocker_family_handoff = $FirstBlockerFamilyHandoff
  first_blocker_family_completion_audit_handoff = $FirstFamilyCompletionAuditHandoff
  summon_anywhere_family_chain_completion_audit_handoff = $FamilyChainCompletionAuditHandoff
  persistent_supervision_required_prerequisites_observed = $PersistentSupervisionRequiredPrerequisitesObserved
  persistent_supervision_missing_required_before_enable = [string[]]@($PersistentSupervisionMissingRequiredBeforeEnable)
  persistent_supervision_first_missing_required_before_enable = $PersistentSupervisionFirstMissingRequiredBeforeEnable
  persistent_supervision_first_missing_requirement_handoff = $PersistentSupervisionFirstMissingRequirementHandoff
  persistent_supervision_required_prerequisites_handoff = $PersistentSupervisionRequiredPrerequisitesHandoff
  latest_activation_execution_handoff_observed = $ActivationExecutionHandoffReady
  latest_activation_execution_handoff = $(if ($ActivationExecutionHandoffReady) { $ActivationExecutionHandoff } else { [ordered]@{} })
  activation_execution_handoff_observed = $ActivationExecutionHandoffReady
  activation_execution_handoff = $(if ($ActivationExecutionHandoffReady) { $ActivationExecutionHandoff } else { [ordered]@{} })
  resident_runtime_candidate_handoff_observed = $ResidentRuntimeCandidateHandoffObserved
  resident_runtime_candidate_handoff = $ResidentRuntimeCandidateHandoff
  checks = $Checks
  governance = [ordered]@{
    diagnostic_only = $true
    read_only_contract = $true
    uses_lens_status_readback = $true
    uses_persistent_supervision_readback = $true
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
