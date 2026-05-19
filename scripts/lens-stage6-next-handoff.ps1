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

function Invoke-JsonScriptReadback {
  param(
    [string]$ScriptPath,
    [hashtable]$Parameters = @{}
  )

  $Output = & $ScriptPath @Parameters 2>&1
  $ExitCode = $LASTEXITCODE
  $Text = ($Output | ForEach-Object { [string]$_ }) -join "`n"

  if ([string]::IsNullOrWhiteSpace($Text)) {
    throw "JSON script readback produced no output: $ScriptPath"
  }

  try {
    $Payload = $Text | ConvertFrom-Json -ErrorAction Stop
  } catch {
    throw "JSON script readback failed to parse: $ScriptPath. $Text"
  }

  return [ordered]@{
    exit_code = [int]$ExitCode
    payload = $Payload
  }
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$StatusReadback = Invoke-LensStatusReadback -StatusLimit $Limit
$Stage6PrerequisiteBringupPlanScript = Join-Path $PSScriptRoot 'lens-stage6-prerequisite-bringup-plan.ps1'
$PersistentSupervisionResidentClaimBoundaryScript = Join-Path $PSScriptRoot 'lens-persistent-supervision-resident-claim-boundary-proof.ps1'
$Stage6PrerequisiteBringupDataDir = [string]$env:FRANCIS_DATA_DIR
if ([string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupDataDir)) {
  $Stage6PrerequisiteBringupDataDir = Join-Path $RepoRoot 'data'
}
$Stage6PrerequisiteBringupPlanResult = Invoke-JsonScriptReadback `
  -ScriptPath $Stage6PrerequisiteBringupPlanScript `
  -Parameters @{ Mode = 'Status'; DataDir = $Stage6PrerequisiteBringupDataDir }
$Stage6PrerequisiteBringupPlan = $Stage6PrerequisiteBringupPlanResult.payload
$Stage6PrerequisiteBringupPlanGovernance = Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'governance' -Default ([ordered]@{})
$Stage6PrerequisiteBringupPlanRequiredBeforeEnable = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'required_before_enable'
)
$Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'missing_required_before_enable'
)
$Stage6PrerequisiteBringupPlanNextOperatorAction = Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_action' -Default ([ordered]@{})
$Stage6PrerequisiteBringupPlanNextOperatorCommand = Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_command' -Default ([ordered]@{})
$Stage6PrerequisiteBringupPlanNextOperatorActorScopeReadiness = Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_actor_scope_readiness' -Default ([ordered]@{})
$Stage6PrerequisiteBringupPlanCommandAvailability = Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'operator_sequence_command_availability' -Default ([ordered]@{})
$Stage6PrerequisiteBringupPlanAllowedFirstMissingTruthfulGaps = @(
  'resident_host_process_not_supervised',
  'resident_supervision_not_persistent',
  'summon_tray_presence_blocker_boundary',
  'os_level_command_palette_binding',
  'summon_overlay_window_blocker_boundary',
  'summon_anywhere_blockers'
)
$Stage6PrerequisiteBringupPlanFirstMissingRequirement = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_first_missing_requirement' -Default '')
$Stage6PrerequisiteBringupPlanFirstMissingTruthfulGap = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_first_missing_truthful_gap' -Default '')
$Stage6PrerequisiteBringupPlanNextOperatorRequirement = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_action_requirement' -Default '')
$Stage6PrerequisiteBringupPlanStatus = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'status' -Default '')
$Stage6PrerequisiteBringupPlanCurrentGap = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_truthful_gap' -Default '')
$Stage6PrerequisiteBringupPlanCurrentGapBasis = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_truthful_gap_basis' -Default '')
$Stage6PrerequisiteBringupNextOperatorActionId = [string](
  Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorAction -Name 'id' -Default ''
)
$Stage6PrerequisiteBringupNextOperatorActionMethod = [string](
  Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorAction -Name 'method' -Default ''
)
$Stage6PrerequisiteBringupNextOperatorCommandMode = [string](
  Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorCommand -Name 'mode' -Default ''
)
$Stage6PrerequisiteBringupPlanCommonObserved = (
  [int]$Stage6PrerequisiteBringupPlanResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'kind' -Default '') -eq 'lens.stage6.prerequisite_bringup.plan' -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'ok' -Default $false) -and
  [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'stage_state' -Default '') -eq 'active' -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'ready_to_close' -Default $true) -and
  [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'acceptance_criterion' -Default '') -eq 'system_resident_presence' -and
  -not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupPlanCurrentGap) -and
  -not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupPlanCurrentGapBasis) -and
  -not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupNextOperatorActionId) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorAction -Name 'script_would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorAction -Name 'script_would_mutate' -Default $true) -and
  -not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupNextOperatorCommandMode) -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanCommandAvailability -Name 'truthful' -Default $false) -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'resident_host_process' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'tray_presence' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'global_hotkey_binding' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'overlay_window' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'summon_binding' -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'plan_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'requires_explicit_operator_execution' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'actor_scope_readback' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'would_mutate' -Default $true)
)
$Stage6PrerequisiteBringupPlanBlockedObserved = (
  $Stage6PrerequisiteBringupPlanCommonObserved -and
  $Stage6PrerequisiteBringupPlanStatus -eq 'blocked' -and
  $Stage6PrerequisiteBringupPlanCurrentGap -eq 'persistent_supervision_required_prerequisites_missing' -and
  $Stage6PrerequisiteBringupPlanCurrentGapBasis -eq 'missing_required_before_enable' -and
  -not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupPlanFirstMissingRequirement) -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains $Stage6PrerequisiteBringupPlanFirstMissingRequirement -and
  $Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable -contains $Stage6PrerequisiteBringupPlanFirstMissingRequirement -and
  $Stage6PrerequisiteBringupPlanAllowedFirstMissingTruthfulGaps -contains $Stage6PrerequisiteBringupPlanFirstMissingTruthfulGap -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'required_before_enable_ready' -Default $true) -and
  $Stage6PrerequisiteBringupPlanNextOperatorRequirement -eq $Stage6PrerequisiteBringupPlanFirstMissingRequirement
)
$Stage6PrerequisiteBringupPlanReadyForEnablementObserved = (
  $Stage6PrerequisiteBringupPlanCommonObserved -and
  $Stage6PrerequisiteBringupPlanStatus -eq 'ready_for_persistent_supervision_enablement_sequence' -and
  @($Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable).Count -eq 0 -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'required_before_enable_ready' -Default $false) -and
  $Stage6PrerequisiteBringupPlanCurrentGapBasis -eq 'persistent_supervision_plan.next_smallest_truthful_gap' -and
  $Stage6PrerequisiteBringupPlanNextOperatorRequirement -eq 'persistent_supervision_enablement'
)
$Stage6PrerequisiteBringupPlanAppliedObserved = (
  $Stage6PrerequisiteBringupPlanCommonObserved -and
  $Stage6PrerequisiteBringupPlanStatus -eq 'persistent_supervision_enablement_applied' -and
  @($Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable).Count -eq 0 -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'required_before_enable_ready' -Default $false) -and
  $Stage6PrerequisiteBringupPlanCurrentGap -ne 'persistent_supervision_required_prerequisites_missing' -and
  @(
    'persistent_supervision_plan.next_smallest_truthful_gap',
    'persistent_supervision_enablement_execution_receipt.post_plan.next_smallest_truthful_gap'
  ) -contains $Stage6PrerequisiteBringupPlanCurrentGapBasis -and
  $Stage6PrerequisiteBringupPlanNextOperatorRequirement -eq 'persistent_supervision_enablement_receipt' -and
  $Stage6PrerequisiteBringupNextOperatorActionId -eq 'review_persistent_supervision_enablement_receipt' -and
  $Stage6PrerequisiteBringupNextOperatorActionMethod -eq 'GET' -and
  $Stage6PrerequisiteBringupNextOperatorCommandMode -eq 'Status'
)
$Stage6PrerequisiteBringupPlanObserved = (
  $Stage6PrerequisiteBringupPlanBlockedObserved -or
  $Stage6PrerequisiteBringupPlanReadyForEnablementObserved -or
  $Stage6PrerequisiteBringupPlanAppliedObserved
)

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
$PersistentSupervisionEnablementAuthorityReadiness = Get-PropertyValue -Payload $ResidentHostReadback -Name 'persistent_supervision_enablement_authority_readiness' -Default ([ordered]@{})
$PersistentSupervisionEnablementExecutionReadiness = Get-PropertyValue -Payload $ResidentHostReadback -Name 'persistent_supervision_enablement_execution_readiness' -Default ([ordered]@{})
$PersistentSupervisionEnablementExecutionReceipts = Get-PropertyValue -Payload $ResidentHostReadback -Name 'persistent_supervision_enablement_execution_receipts' -Default ([ordered]@{})
$PersistentSupervisionEnablementExecutionReceiptLatest = Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'latest' -Default ([ordered]@{})
$PersistentSupervisionEnablementExecutionReceiptGovernance = Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'governance' -Default ([ordered]@{})
$PersistentSupervisionEnablementExecutionReceiptPostPlan = Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptLatest -Name 'post_plan' -Default ([ordered]@{})
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
$FirstMissingHandoffIsLiveUnsupervisedProcess = (
  [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'blocker' -Default '') -eq 'resident_host_process_not_supervised' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'requirement_state' -Default '') -eq 'foreground_observed_not_supervised'
)
$EnablementAuthorityBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'blockers' -Default @()
)
$EnablementExecutionBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'blockers' -Default @()
)
$PersistentSupervisionEnablementAuthorityHandoffObserved = (
  [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_enablement_authority.readiness_audit' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'status' -Default '') -eq 'blocked' -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'boundary_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'grant_boundary_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'grant_receipt_readback_ready' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'enablement_authority_granted' -Default $true) -and
  $EnablementAuthorityBlockers -contains 'persistent_supervision_enablement_authority_not_granted' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_enablement_execution.readiness_audit' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'status' -Default '') -eq 'blocked' -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'boundary_observed' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'persistent_supervision_execution_authority' -Default $true) -and
  $EnablementExecutionBlockers -contains 'persistent_supervision_execution_authority_not_granted' -and
  -not $Stage6PrerequisiteBringupPlanAppliedObserved -and
  -not $FirstMissingHandoffIsLiveUnsupervisedProcess
)
$PersistentSupervisionEnablementAuthorityHandoff = [ordered]@{}
if ($PersistentSupervisionEnablementAuthorityHandoffObserved) {
  $PersistentSupervisionEnablementAuthorityHandoff = [ordered]@{
    status = 'blocked'
    previous_next_smallest_truthful_gap = 'persistent_supervision_authority_not_granted'
    consumed_audit_next_smallest_truthful_gap = 'persistent_supervision_enablement_denial_boundary'
    next_smallest_truthful_gap = 'persistent_supervision_enablement_authority_not_granted'
    next_step = 'prove_persistent_supervision_enablement_authority_after_candidate_handoff'
    proof_script = 'scripts/lens-persistent-supervision-enablement-authority-proof.ps1 -Mode Status'
    route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'enablement_route' -Default '/lens/host/persistent-supervision/enablement')
    request_route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'request_route' -Default '')
    grant_route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'authority_route' -Default '')
    grants_route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'grants_route' -Default '')
    readiness_route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'route' -Default '')
    execution_readiness_route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'route' -Default '')
    authority_required = 'persistent_supervision_enablement_authority'
    authority_granted = $false
    enablement_denial_observed = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'boundary_observed' -Default $false)
    execution_denial_observed = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'boundary_observed' -Default $false)
    persistent_supervision_enablement_authority = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'enablement_authority_granted' -Default $false)
    service_config_write_authority = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'service_config_write_authority' -Default $false)
    persistent_supervision_execution_authority = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'persistent_supervision_execution_authority' -Default $false)
    receipt_write_authority = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'receipt_write_authority' -Default $false)
    resident_claim_authority = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'resident_claim_authority' -Default $false)
    resident_claim_allowed = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'resident_claim_allowed' -Default $false)
    service_config_updated = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementAuthorityReadiness -Name 'service_config_updated' -Default $false)
    applied = $false
    executed = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReadiness -Name 'executed' -Default $false)
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
    blockers = [string[]]@($EnablementAuthorityBlockers + $EnablementExecutionBlockers | Sort-Object -Unique)
  }
}
$PersistentSupervisionEnablementExecutionReceiptStatus = [string](
  Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptLatest -Name 'status' -Default ''
)
$PersistentSupervisionEnablementReceiptReviewObserved = (
  $Stage6PrerequisiteBringupPlanAppliedObserved -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_enablement_execution.receipts' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'status' -Default '') -eq 'readback_ready' -and
  [int](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'total' -Default 0) -gt 0 -and
  @('service_config_updated', 'service_config_already_enabled') -contains $PersistentSupervisionEnablementExecutionReceiptStatus -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'persistent_supervision_enablement_allowed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'persistent_supervision_ready' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'resident_claim_allowed' -Default $true) -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptPostPlan -Name 'next_smallest_truthful_gap' -Default '') -eq 'persistent_supervision_execution_boundary' -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptGovernance -Name 'read_only_contract' -Default $false) -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptGovernance -Name 'next_step' -Default '') -eq 'review_persistent_supervision_execution_receipts_before_resident_claim_boundary' -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptGovernance -Name 'resident_claim_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptGovernance -Name 'mutation_authority_granted' -Default $true)
)
$PersistentSupervisionEnablementReceiptReviewHandoff = [ordered]@{}
if ($PersistentSupervisionEnablementReceiptReviewObserved) {
  $PersistentSupervisionEnablementReceiptReviewHandoff = [ordered]@{
    status = 'receipt_reviewed'
    previous_next_smallest_truthful_gap = 'persistent_supervision_execution_boundary'
    next_smallest_truthful_gap = 'persistent_supervision_resident_claim_authority_boundary'
    next_step = 'review_persistent_supervision_resident_claim_boundary_without_runtime_start'
    proof_script = 'scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status'
    route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'route' -Default '/lens/host/persistent-supervision/enablement/executions')
    readiness_route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'readiness_route' -Default '/lens/host/persistent-supervision/enablement/execution/readiness')
    execution_route = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceipts -Name 'execution_route' -Default '/lens/host/persistent-supervision/enablement/execution')
    latest_receipt_id = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptLatest -Name 'receipt_id' -Default '')
    latest_receipt_status = $PersistentSupervisionEnablementExecutionReceiptStatus
    post_plan_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionReceiptPostPlan -Name 'next_smallest_truthful_gap' -Default '')
    authority_required = 'resident_claim_authority'
    authority_granted = $false
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
  }
}
$PersistentSupervisionResidentClaimBoundaryResult = [ordered]@{
  exit_code = 0
  payload = [ordered]@{}
}
$PersistentSupervisionResidentClaimBoundary = [ordered]@{}
$PersistentSupervisionResidentClaimBoundaryHandoff = [ordered]@{}
if ($PersistentSupervisionEnablementReceiptReviewObserved) {
  if (-not (Test-Path -LiteralPath $PersistentSupervisionResidentClaimBoundaryScript -PathType Leaf)) {
    throw "Required Lens proof script is missing: $PersistentSupervisionResidentClaimBoundaryScript"
  }
  $PersistentSupervisionResidentClaimBoundaryResult = Invoke-JsonScriptReadback `
    -ScriptPath $PersistentSupervisionResidentClaimBoundaryScript `
    -Parameters @{ Mode = 'Status' }
  $PersistentSupervisionResidentClaimBoundary = Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryResult -Name 'payload' -Default ([ordered]@{})
  $PersistentSupervisionResidentClaimBoundaryHandoff = Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'handoff' -Default ([ordered]@{})
}
$PersistentSupervisionResidentClaimBoundaryHandoffObserved = (
  $PersistentSupervisionEnablementReceiptReviewObserved -and
  [int](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryResult -Name 'exit_code' -Default 1) -eq 0 -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'kind' -Default '') -eq 'lens.host.persistent_supervision_resident_claim_boundary.proof' -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'ok' -Default $false) -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'final_persistent_supervision_authority_family_consumed' -Default $false) -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'recommended_handoff_source' -Default '') -eq 'persistent_supervision_resident_claim_boundary_handoff' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'recommended_next_slice' -Default '') -eq 'run_stage6_lens_completion_audit_after_resident_claim_boundary_readback' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'recommended_proof_script' -Default '') -eq 'scripts/lens-stage6-completion-audit.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'authority_required' -Default '') -eq 'none_new_stage6_completion_audit' -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'authority_granted' -Default $true) -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'status' -Default '') -eq 'audit_needed' -and
  [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit' -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'would_mutate' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'would_claim_resident' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'would_supervise_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'would_write_receipt' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'would_write_memory' -Default $true)
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
    authority_granted = $false
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
$AuthorityGranted = [bool](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'authority_granted' -Default $false)
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
  $AuthorityGranted = [bool](Get-PropertyValue -Payload $FirstFamilyCompletionAuditHandoff -Name 'authority_granted' -Default $false)
}
if ($PersistentSupervisionRequiredPrerequisitesObserved) {
  $RecommendedHandoffSource = 'persistent_supervision_required_prerequisites_handoff'
  $RecommendedNextGap = 'persistent_supervision_required_prerequisites_missing'
  $RecommendedNextSlice = 'resolve_persistent_supervision_required_prerequisites_before_enablement'
  $RecommendedProofScript = 'scripts/lens-persistent-supervision-prerequisites-proof.ps1 -Mode Status'
  $RecommendedRoute = '/lens/host/persistent-supervision'
  $RecommendedReadinessRoute = '/lens/host/persistent-supervision/enablement'
  $AuthorityRequired = 'resident_host_process_tray_hotkey_overlay_and_summon_prerequisites'
  $AuthorityGranted = [bool](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'authority_granted' -Default $false)
}
if ($PersistentSupervisionFirstMissingRequirementHandoffReady) {
  $FirstMissingNextGap = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'next_smallest_truthful_gap' -Default '')
  $FirstMissingNextSlice = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'next_step' -Default '')
  $FirstMissingProofScript = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'proof_script' -Default '')
  $FirstMissingRoute = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'route' -Default '')
  $FirstMissingReadinessRoute = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'readiness_route' -Default '')
  $FirstMissingAuthorityRequired = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'authority_required' -Default '')
  $FirstMissingAuthorityGranted = [bool](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'authority_granted' -Default $false)

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
    $AuthorityGranted = $FirstMissingAuthorityGranted
  }
}
if ($PersistentSupervisionEnablementAuthorityHandoffObserved) {
  $RecommendedHandoffSource = 'persistent_supervision_enablement_authority_denial_handoff'
  $RecommendedNextGap = [string]$PersistentSupervisionEnablementAuthorityHandoff.next_smallest_truthful_gap
  $RecommendedNextSlice = [string]$PersistentSupervisionEnablementAuthorityHandoff.next_step
  $RecommendedProofScript = [string]$PersistentSupervisionEnablementAuthorityHandoff.proof_script
  $RecommendedRoute = [string]$PersistentSupervisionEnablementAuthorityHandoff.route
  $RecommendedReadinessRoute = [string]$PersistentSupervisionEnablementAuthorityHandoff.readiness_route
  $AuthorityRequired = [string]$PersistentSupervisionEnablementAuthorityHandoff.authority_required
  $AuthorityGranted = [bool]$PersistentSupervisionEnablementAuthorityHandoff.authority_granted
}
if ($ActivationExecutionHandoffReady) {
  $ActivationExecutionNextGap = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'next_smallest_truthful_gap' -Default '')
  $ActivationExecutionNextSlice = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'next_step' -Default '')
  $ActivationExecutionProofScript = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'proof_script' -Default '')
  $ActivationExecutionRoute = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'route' -Default '')
  $ActivationExecutionReadinessRoute = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'readiness_route' -Default '')
  $ActivationExecutionAuthorityRequired = [string](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'authority_required' -Default '')
  $ActivationExecutionAuthorityGranted = [bool](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'authority_granted' -Default $false)

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
    $AuthorityGranted = $ActivationExecutionAuthorityGranted
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
  $AuthorityGranted = [bool](Get-PropertyValue -Payload $ResidentRuntimeCandidateHandoff -Name 'authority_granted' -Default $false)
}
$Stage6PrerequisiteBringupCommandMode = [string](
  Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorCommand -Name 'mode' -Default 'Status'
)
$Stage6PrerequisiteBringupNextOperatorActionId = [string](
  Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorAction -Name 'id' -Default ''
)
$Stage6PrerequisiteBringupCommandModeSlug = switch ($Stage6PrerequisiteBringupCommandMode) {
  'RequestNext' { 'request_next' }
  'GrantNext' { 'grant_next' }
  'ExecuteNext' { 'execute_next' }
  default { 'status' }
}
if ($Stage6PrerequisiteBringupNextOperatorActionId.StartsWith('await_')) {
  $Stage6PrerequisiteBringupCommandModeSlug = 'approval_wait'
}
$Stage6PrerequisiteBringupRecommendedNextStep = (
  "run_stage6_prerequisite_bringup_$Stage6PrerequisiteBringupCommandModeSlug`_for_$([string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_action_requirement' -Default 'resident_host_process'))"
)
if ($Stage6PrerequisiteBringupPlanAppliedObserved) {
  $Stage6PrerequisiteBringupRecommendedNextStep = $Stage6PrerequisiteBringupNextOperatorActionId
}
$Stage6PrerequisiteBringupRecommendedNextGap = $Stage6PrerequisiteBringupPlanCurrentGap
if ($Stage6PrerequisiteBringupPlanBlockedObserved) {
  $Stage6PrerequisiteBringupRecommendedNextGap = 'persistent_supervision_required_prerequisites_missing'
}
$Stage6PrerequisiteBringupAuthorityRequired = 'resident_host_process_tray_hotkey_overlay_and_summon_prerequisites'
$Stage6PrerequisiteBringupAuthorityGranted = $false
if ($Stage6PrerequisiteBringupPlanReadyForEnablementObserved) {
  $Stage6PrerequisiteBringupAuthorityRequired = 'persistent_supervision_enablement_sequence_authority'
}
if ($Stage6PrerequisiteBringupPlanAppliedObserved) {
  $Stage6PrerequisiteBringupAuthorityRequired = 'none_readback_only'
  $Stage6PrerequisiteBringupAuthorityGranted = $true
}
$Stage6PrerequisiteBringupOperatorPlanHandoff = [ordered]@{}
if ($Stage6PrerequisiteBringupPlanObserved) {
  $Stage6PrerequisiteBringupOperatorPlanHandoff = [ordered]@{
    status = $Stage6PrerequisiteBringupPlanStatus
    next_smallest_truthful_gap = $Stage6PrerequisiteBringupRecommendedNextGap
    next_step = $Stage6PrerequisiteBringupRecommendedNextStep
    proof_script = 'scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status'
    route = '/lens/host/persistent-supervision'
    readiness_route = '/lens/host/persistent-supervision/enablement'
    operator_plan_script = 'scripts/lens-stage6-prerequisite-bringup-plan.ps1'
    current_truthful_gap = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_truthful_gap' -Default '')
    current_truthful_gap_basis = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_truthful_gap_basis' -Default '')
    current_first_missing_requirement = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_first_missing_requirement' -Default '')
    current_first_missing_truthful_gap = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_first_missing_truthful_gap' -Default '')
    next_operator_action_requirement = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_action_requirement' -Default '')
    next_operator_action = $Stage6PrerequisiteBringupPlanNextOperatorAction
    next_operator_command = $Stage6PrerequisiteBringupPlanNextOperatorCommand
    next_operator_actor_scope_readiness = $Stage6PrerequisiteBringupPlanNextOperatorActorScopeReadiness
    operator_sequence_command_availability = $Stage6PrerequisiteBringupPlanCommandAvailability
    required_before_enable = [string[]]@($Stage6PrerequisiteBringupPlanRequiredBeforeEnable)
    missing_required_before_enable = [string[]]@($Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable)
    required_before_enable_ready = [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'required_before_enable_ready' -Default $false)
    first_missing_requirement_handoff = $(Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'first_missing_requirement_handoff' -Default ([ordered]@{}))
    authority_required = $Stage6PrerequisiteBringupAuthorityRequired
    authority_granted = $Stage6PrerequisiteBringupAuthorityGranted
    read_only_contract = $true
    diagnostic_only = $true
    plan_only = $true
    requires_explicit_operator_execution = $true
    would_execute = $false
    would_mutate = $false
    blockers = [string[]]@(@(
        [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_truthful_gap' -Default ''),
        [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_first_missing_truthful_gap' -Default '')
      ) | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Sort-Object -Unique)
  }
}
if ($Stage6PrerequisiteBringupPlanObserved) {
  $RecommendedHandoffSource = 'stage6_prerequisite_bringup_operator_plan'
  $RecommendedNextGap = [string]$Stage6PrerequisiteBringupOperatorPlanHandoff.next_smallest_truthful_gap
  $RecommendedNextSlice = [string]$Stage6PrerequisiteBringupOperatorPlanHandoff.next_step
  $RecommendedProofScript = [string]$Stage6PrerequisiteBringupOperatorPlanHandoff.proof_script
  $RecommendedRoute = [string]$Stage6PrerequisiteBringupOperatorPlanHandoff.route
  $RecommendedReadinessRoute = [string]$Stage6PrerequisiteBringupOperatorPlanHandoff.readiness_route
  $AuthorityRequired = [string]$Stage6PrerequisiteBringupOperatorPlanHandoff.authority_required
  $AuthorityGranted = [bool]$Stage6PrerequisiteBringupOperatorPlanHandoff.authority_granted
}
if ($PersistentSupervisionEnablementReceiptReviewObserved) {
  $RecommendedHandoffSource = 'persistent_supervision_enablement_receipt_review_handoff'
  $RecommendedNextGap = [string]$PersistentSupervisionEnablementReceiptReviewHandoff.next_smallest_truthful_gap
  $RecommendedNextSlice = [string]$PersistentSupervisionEnablementReceiptReviewHandoff.next_step
  $RecommendedProofScript = [string]$PersistentSupervisionEnablementReceiptReviewHandoff.proof_script
  $RecommendedRoute = [string]$PersistentSupervisionEnablementReceiptReviewHandoff.route
  $RecommendedReadinessRoute = [string]$PersistentSupervisionEnablementReceiptReviewHandoff.readiness_route
  $AuthorityRequired = [string]$PersistentSupervisionEnablementReceiptReviewHandoff.authority_required
  $AuthorityGranted = [bool]$PersistentSupervisionEnablementReceiptReviewHandoff.authority_granted
}
if ($PersistentSupervisionResidentClaimBoundaryHandoffObserved) {
  $RecommendedHandoffSource = 'persistent_supervision_resident_claim_boundary_handoff'
  $RecommendedNextGap = [string]$PersistentSupervisionResidentClaimBoundaryHandoff.next_smallest_truthful_gap
  $RecommendedNextSlice = [string]$PersistentSupervisionResidentClaimBoundaryHandoff.next_step
  $RecommendedProofScript = [string]$PersistentSupervisionResidentClaimBoundaryHandoff.proof_script
  $RecommendedRoute = [string]$PersistentSupervisionResidentClaimBoundaryHandoff.route
  $RecommendedReadinessRoute = [string]$PersistentSupervisionResidentClaimBoundaryHandoff.readiness_route
  $AuthorityRequired = [string]$PersistentSupervisionResidentClaimBoundaryHandoff.authority_required
  $AuthorityGranted = [bool]$PersistentSupervisionResidentClaimBoundaryHandoff.authority_granted
}
$RecommendedFirstMissingAuthorityRequired = [string](
  Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'authority_required' -Default ''
)
$FirstMissingHandoffNextGap = [string](
  Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'next_smallest_truthful_gap' -Default ''
)
if ($PersistentSupervisionFirstMissingRequirementHandoffReady) {
  if ($FirstMissingHandoffNextGap -eq 'resident_host_process_not_supervised') {
    $RecommendedFirstMissingAuthorityRequired = 'process_supervision_authority'
  } elseif ($FirstMissingHandoffNextGap -eq 'resident_supervision_not_persistent') {
    $RecommendedFirstMissingAuthorityRequired = 'persistent_process_supervision_authority'
  }
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
  -not [bool](Get-PropertyValue -Payload $ActivationExecutionHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupOperatorPlanHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupOperatorPlanHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementReceiptReviewHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementReceiptReviewHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryHandoff -Name 'would_mutate' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorAction -Name 'script_would_execute' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorAction -Name 'script_would_mutate' -Default $false)
)
$PersistentSupervisionRequiredPrerequisitesCheckPassed = (
  $PersistentSupervisionRequiredPrerequisitesObserved -or
  $Stage6PrerequisiteBringupPlanReadyForEnablementObserved -or
  $Stage6PrerequisiteBringupPlanAppliedObserved
)
$PersistentSupervisionRequiredPrerequisitesCheckStatus = if ($Stage6PrerequisiteBringupPlanAppliedObserved) {
  'not_applicable_enablement_applied'
} elseif ($PersistentSupervisionRequiredPrerequisitesObserved) {
  'required_prerequisites_handoff_ready'
} elseif ($Stage6PrerequisiteBringupPlanReadyForEnablementObserved) {
  'not_applicable_prerequisites_ready'
} else {
  'missing_or_unexpected'
}
$PersistentSupervisionFirstMissingRequirementCheckPassed = (
  $PersistentSupervisionFirstMissingRequirementHandoffReady -or
  $Stage6PrerequisiteBringupPlanReadyForEnablementObserved -or
  $Stage6PrerequisiteBringupPlanAppliedObserved
)
$PersistentSupervisionFirstMissingRequirementCheckStatus = if ($Stage6PrerequisiteBringupPlanAppliedObserved) {
  'not_applicable_enablement_applied'
} elseif ($PersistentSupervisionFirstMissingRequirementHandoffReady) {
  'first_missing_requirement_handoff_ready'
} elseif ($Stage6PrerequisiteBringupPlanReadyForEnablementObserved) {
  'not_applicable_prerequisites_ready'
} else {
  'missing_or_unexpected'
}

$Checks = @(
  New-Check -Id 'closure_readback' -Status 'blocked_closure_readback_observed' -Passed $ClosureObserved -Evidence '/lens/status stage6_readiness.closure_readback' -Reason 'Stage 6 closure must remain blocked before transition.'
  New-Check -Id 'stage_boundary' -Status 'stage6_active' -Passed $StageBoundaryObserved -Evidence '/lens/status stage6_readiness' -Reason 'The next handoff only applies while Stage 6 is active.'
  New-Check -Id 'first_blocked_criterion' -Status 'summon_anywhere_blocked' -Passed $FirstBlockedCriterionObserved -Evidence 'closure_readback.blocked_criteria[0]' -Reason 'Summon-anywhere is still the first blocked acceptance criterion.'
  New-Check -Id 'first_blocker_family_handoff' -Status 'resident_host_handoff_ready' -Passed $FirstFamilyHandoffObserved -Evidence 'summon_anywhere.handoff.first_blocker_family_handoff' -Reason 'The next concrete handoff points at the resident host runtime boundary.'
  New-Check -Id 'completion_audit_handoff' -Status 'process_supervision_audit_handoff_ready' -Passed $CompletionAuditHandoffObserved -Evidence 'summon_anywhere.handoff.first_blocker_family_completion_audit_handoff' -Reason 'The process-supervision handoff is present but diagnostic-only.'
  New-Check -Id 'family_chain_handoff' -Status 'summon_family_chain_handoff_ready' -Passed $FamilyChainHandoffObserved -Evidence 'summon_anywhere.handoff.summon_anywhere_family_chain_completion_audit_handoff' -Reason 'The summon blocker family chain can still be consumed by audit.'
  New-Check -Id 'persistent_supervision_required_prerequisites' -Status $PersistentSupervisionRequiredPrerequisitesCheckStatus -Passed $PersistentSupervisionRequiredPrerequisitesCheckPassed -Evidence '/lens/status resident_host.persistent_supervision_plan missing_required_before_enable' -Reason 'The latest Stage 6 handoff must preserve the full persistent-supervision prerequisite map after the audit chain consumes the older resident-host proofs, or explicitly report that the prerequisite chain is already ready/applied.'
  New-Check -Id 'persistent_supervision_first_missing_requirement' -Status $PersistentSupervisionFirstMissingRequirementCheckStatus -Passed $PersistentSupervisionFirstMissingRequirementCheckPassed -Evidence '/lens/status resident_host.persistent_supervision_plan first_missing_requirement_handoff' -Reason 'The persistent-supervision prerequisite gap must name the first concrete missing prerequisite before the next slice, unless the governed bring-up plan has already advanced beyond missing prerequisites.'
  New-Check -Id 'stage6_prerequisite_bringup_plan' -Status $(if ($Stage6PrerequisiteBringupPlanObserved) { 'operator_plan_readback_ready' } else { 'missing_or_unexpected' }) -Passed $Stage6PrerequisiteBringupPlanObserved -Evidence 'scripts/lens-stage6-prerequisite-bringup-plan.ps1 -Mode Status' -Reason 'The next handoff should point at the governed prerequisite bring-up runbook instead of lower-level proof fragments.'
  New-Check -Id 'persistent_supervision_enablement_receipt_review' -Status $(if ($PersistentSupervisionEnablementReceiptReviewObserved) { 'receipt_reviewed' } elseif ($Stage6PrerequisiteBringupPlanAppliedObserved) { 'missing_or_unexpected' } else { 'not_applicable' }) -Passed $(-not $Stage6PrerequisiteBringupPlanAppliedObserved -or $PersistentSupervisionEnablementReceiptReviewObserved) -Evidence '/lens/status resident_host.persistent_supervision_enablement_execution_receipts' -Reason 'After enablement is applied, the next handoff must consume the read-only receipt review before advancing to resident-claim boundary review.'
  New-Check -Id 'persistent_supervision_resident_claim_boundary_review' -Status $(if ($PersistentSupervisionResidentClaimBoundaryHandoffObserved) { 'resident_claim_boundary_consumed' } elseif ($PersistentSupervisionEnablementReceiptReviewObserved) { 'missing_or_unexpected' } else { 'not_applicable' }) -Passed $(-not $PersistentSupervisionEnablementReceiptReviewObserved -or $PersistentSupervisionResidentClaimBoundaryHandoffObserved) -Evidence 'scripts/lens-persistent-supervision-resident-claim-boundary-proof.ps1 -Mode Status' -Reason 'After enablement receipt review, the next handoff must consume the read-only resident-claim boundary before routing to the Stage 6 completion audit.'
  New-Check -Id 'persistent_supervision_enablement_authority_handoff' -Status $(if ($PersistentSupervisionEnablementAuthorityHandoffObserved) { 'enablement_authority_handoff_ready' } else { 'not_observed' }) -Passed $true -Evidence '/lens/status resident_host.persistent_supervision_enablement_authority_readiness' -Reason 'When the enablement authority denial and execution-denial readiness are already audited, the next handoff can point at the enablement-authority proof without granting authority.'
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
  authority_granted = $AuthorityGranted
  stage6_prerequisite_bringup_plan_observed = $Stage6PrerequisiteBringupPlanObserved
  stage6_prerequisite_bringup_operator_plan_handoff = $Stage6PrerequisiteBringupOperatorPlanHandoff
  persistent_supervision_enablement_receipt_review_handoff_observed = $PersistentSupervisionEnablementReceiptReviewObserved
  persistent_supervision_enablement_receipt_review_handoff = $PersistentSupervisionEnablementReceiptReviewHandoff
  persistent_supervision_resident_claim_boundary_handoff_observed = $PersistentSupervisionResidentClaimBoundaryHandoffObserved
  persistent_supervision_resident_claim_boundary_handoff = $PersistentSupervisionResidentClaimBoundaryHandoff
  persistent_supervision_resident_claim_boundary_proof = [ordered]@{
    status = [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'status' -Default '')
    ok = [bool](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'ok' -Default $false)
    exit_code = [int](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundaryResult -Name 'exit_code' -Default 0)
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'next_smallest_truthful_gap' -Default '')
    recommended_next_slice = [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'recommended_next_slice' -Default '')
    recommended_proof_script = [string](Get-PropertyValue -Payload $PersistentSupervisionResidentClaimBoundary -Name 'recommended_proof_script' -Default '')
  }
  next_operator_action_requirement = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_action_requirement' -Default '')
  next_operator_action = $Stage6PrerequisiteBringupPlanNextOperatorAction
  next_operator_command = $Stage6PrerequisiteBringupPlanNextOperatorCommand
  next_operator_actor_scope_readiness = $Stage6PrerequisiteBringupPlanNextOperatorActorScopeReadiness
  operator_sequence_command_availability = $Stage6PrerequisiteBringupPlanCommandAvailability
  recommended_prerequisites_handoff_source = $(if ($PersistentSupervisionRequiredPrerequisitesObserved) { 'persistent_supervision_required_prerequisites_handoff' } else { '' })
  recommended_prerequisites_next_slice = [string](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'next_step' -Default '')
  recommended_prerequisites_proof_script = [string](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'proof_script' -Default '')
  recommended_prerequisites_route = [string](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'route' -Default '')
  recommended_prerequisites_readiness_route = [string](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'readiness_route' -Default '')
  recommended_prerequisites_authority_required = [string](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'authority_required' -Default '')
  recommended_prerequisites_authority_granted = [bool](Get-PropertyValue -Payload $PersistentSupervisionRequiredPrerequisitesHandoff -Name 'authority_granted' -Default $false)
  recommended_first_missing_handoff_source = $(if ($PersistentSupervisionFirstMissingRequirementHandoffReady) { 'persistent_supervision_first_missing_requirement_handoff' } else { '' })
  recommended_first_missing_next_slice = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'next_step' -Default '')
  recommended_first_missing_proof_script = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'proof_script' -Default '')
  recommended_first_missing_route = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'route' -Default '')
  recommended_first_missing_readiness_route = [string](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'readiness_route' -Default '')
  recommended_first_missing_authority_required = $RecommendedFirstMissingAuthorityRequired
  recommended_first_missing_authority_granted = [bool](Get-PropertyValue -Payload $PersistentSupervisionFirstMissingRequirementHandoff -Name 'authority_granted' -Default $false)
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
  persistent_supervision_enablement_authority_handoff_observed = $PersistentSupervisionEnablementAuthorityHandoffObserved
  persistent_supervision_enablement_authority_handoff = $PersistentSupervisionEnablementAuthorityHandoff
  stage6_prerequisite_bringup_plan = [ordered]@{
    status = if ($Stage6PrerequisiteBringupPlanObserved) { [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'status' -Default '') } else { 'missing_or_failed' }
    ok = $Stage6PrerequisiteBringupPlanObserved
    exit_code = [int]$Stage6PrerequisiteBringupPlanResult.exit_code
    evidence = [string[]]@(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'evidence'))
    current_truthful_gap = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_truthful_gap' -Default '')
    current_truthful_gap_basis = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_truthful_gap_basis' -Default '')
    current_first_missing_requirement = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_first_missing_requirement' -Default '')
    current_first_missing_truthful_gap = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_first_missing_truthful_gap' -Default '')
    required_before_enable = [string[]]@($Stage6PrerequisiteBringupPlanRequiredBeforeEnable)
    missing_required_before_enable = [string[]]@($Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable)
    required_before_enable_ready = [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'required_before_enable_ready' -Default $false)
    next_operator_action_requirement = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_action_requirement' -Default '')
    next_operator_action = $Stage6PrerequisiteBringupPlanNextOperatorAction
    next_operator_command = $Stage6PrerequisiteBringupPlanNextOperatorCommand
    next_operator_actor_scope_readiness = $Stage6PrerequisiteBringupPlanNextOperatorActorScopeReadiness
    operator_sequence_command_availability = $Stage6PrerequisiteBringupPlanCommandAvailability
    governance = $Stage6PrerequisiteBringupPlanGovernance
  }
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
    uses_stage6_prerequisite_bringup_plan_readback = $true
    stage6_prerequisite_bringup_plan_readback = $Stage6PrerequisiteBringupPlanObserved
    stage6_prerequisite_bringup_actor_scope_readback = [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'actor_scope_readback' -Default $false)
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
