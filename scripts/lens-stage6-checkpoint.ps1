[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(5, 60)]
  [int]$StartupTimeoutSeconds = 30,

  [ValidateRange(2, 30)]
  [int]$HostLaunchRunSeconds = 3,

  [ValidateRange(2, 30)]
  [int]$ResidentSurfaceForegroundRunSeconds = 15,

  [ValidateRange(3, 30)]
  [int]$SupervisorRunSeconds = 20
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function Get-PropertyValue {
  param(
    [object]$Payload,
    [string]$Name,
    [object]$Default = $null
  )

  if ($null -eq $Payload) {
    return $Default
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property) {
    return $Default
  }
  if ($null -eq $Property.Value) {
    return $Default
  }
  return $Property.Value
}

function ConvertTo-StringArray {
  param([object]$Value)

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

function Get-PowerShellPath {
  try {
    $Current = Get-Process -Id $PID -ErrorAction Stop
    if (-not [string]::IsNullOrWhiteSpace([string]$Current.Path)) {
      return [string]$Current.Path
    }
  } catch {
  }

  $Pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
  if ($null -ne $Pwsh) {
    return [string]$Pwsh.Source
  }
  $WindowsPowerShell = Get-Command powershell -ErrorAction SilentlyContinue
  if ($null -ne $WindowsPowerShell) {
    return [string]$WindowsPowerShell.Source
  }
  return ''
}

function Invoke-JsonScript {
  param(
    [string]$PowerShellPath,
    [string]$ScriptPath,
    [string[]]$ScriptArgs = @()
  )

  if ([string]::IsNullOrWhiteSpace($PowerShellPath) -or -not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
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

function Invoke-JsonScriptWithProofRetry {
  param(
    [string]$PowerShellPath,
    [string]$ScriptPath,
    [string[]]$ScriptArgs = @(),
    [string]$ExpectedKind,
    [int]$Attempts = 2
  )

  $LastProof = $null
  for ($Attempt = 1; $Attempt -le $Attempts; $Attempt++) {
    $Result = @(Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $ScriptPath -ScriptArgs $ScriptArgs)
    $Proof = if ($Result.Count -gt 0) { $Result[-1] } else { $null }
    $LastProof = $Proof
    $ExitCode = -1
    $Payload = $null
    if ($Proof -is [System.Collections.IDictionary]) {
      if ($Proof.Contains('exit_code') -and $null -ne $Proof['exit_code']) {
        $ExitCode = [int]$Proof['exit_code']
      }
      if ($Proof.Contains('payload') -and $null -ne $Proof['payload']) {
        $Payload = $Proof['payload']
      }
    }
    if (
      $ExitCode -eq 0 -and
      [string](Get-PropertyValue -Payload $Payload -Name 'kind' -Default '') -eq $ExpectedKind -and
      [string](Get-PropertyValue -Payload $Payload -Name 'status' -Default '') -eq 'proof_passed'
    ) {
      return $Proof
    }
    if ($Attempt -lt $Attempts) {
      Start-Sleep -Milliseconds 500
    }
  }
  return $LastProof
}

function Get-LensStatus {
  $Python = Get-Command python -ErrorAction SilentlyContinue
  if ($null -eq $Python) {
    return [ordered]@{
      ok = $false
      error = 'python_unavailable'
    }
  }

  $Source = @'
import json
from francis.lens.status import lens_status
print(json.dumps(lens_status(limit=3)))
'@
  $Output = & $Python.Source -c $Source
  if ($LASTEXITCODE -ne 0) {
    return [ordered]@{
      ok = $false
      error = 'lens_status_failed'
      exit_code = $LASTEXITCODE
      output = ($Output -join "`n")
    }
  }

  try {
    return ($Output -join "`n") | ConvertFrom-Json -ErrorAction Stop
  } catch {
    return [ordered]@{
      ok = $false
      error = 'lens_status_json_invalid'
      message = [string]$_.Exception.Message
    }
  }
}

function Get-ReadinessCriterion {
  param(
    [object]$LensStatus,
    [string]$CriterionId
  )

  $Readiness = Get-PropertyValue -Payload $LensStatus -Name 'stage6_readiness'
  $Criteria = Get-PropertyValue -Payload $Readiness -Name 'criteria' -Default @()
  foreach ($Criterion in @($Criteria)) {
    if ((Get-PropertyValue -Payload $Criterion -Name 'id' -Default '') -eq $CriterionId) {
      return $Criterion
    }
  }
  return $null
}

function New-Criterion {
  param(
    [string]$Id,
    [string]$Label,
    [string]$Status,
    [bool]$Ready,
    [string[]]$Evidence = @(),
    [string[]]$Blockers = @(),
    [string]$Basis = ''
  )

  return [ordered]@{
    id = $Id
    label = $Label
    status = $Status
    ready = $Ready
    evidence = @($Evidence)
    blockers = @($Blockers)
    basis = $Basis
  }
}

$LensStatus = Get-LensStatus
$LensStatusOk = [bool](Get-PropertyValue -Payload $LensStatus -Name 'ok' -Default $false)
$Stage6Readiness = Get-PropertyValue -Payload $LensStatus -Name 'stage6_readiness'
$StageClaim = [string](Get-PropertyValue -Payload $Stage6Readiness -Name 'claim' -Default 'unavailable')

$SummonCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'summon_anywhere'
$ModeCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'mode_visibility'
$HudCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'hud_layer_runtime'
$HostCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_host_runtime'
$HostSupervisionAuthorityCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_host_supervision_authority_preflight'
$HostSupervisionAuthorityDenialCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_host_supervision_authority_denial_boundary'
$HostSupervisionAuthorityDenialReceiptsCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_host_supervision_authority_denial_receipt_readback'
$HostSupervisionAuthorityGrantReceiptsCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_host_supervision_authority_grant_receipt_readback'
$HostSupervisionAuthorityReadinessCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_host_supervision_authority_readiness_audit'
$PersistentSupervisionEnablementDenialCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'persistent_supervision_enablement_denial_boundary'
$PersistentSupervisionEnablementExecutionDenialCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'persistent_supervision_enablement_execution_denial_boundary'
$RuntimePlanCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_runtime_activation_plan'
$RuntimeGrantCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_runtime_authority_grant_preflight'
$RuntimePolicyCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_runtime_execution_policy_contract'
$RuntimeAuthorityGrantCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_runtime_execution_authority_grant_boundary'
$RuntimeAuthorityGrantReceiptsCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_runtime_authority_grant_receipt_readback'
$RuntimeAuthorityGrantDenialReceiptsCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_runtime_authority_grant_denial_receipt_readback'
$RuntimeAuthorityGrantReadinessCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_runtime_authority_grant_readiness_audit'
$RuntimeBoundaryCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_runtime_authority_boundary'
$PilotIndicator = Get-PropertyValue -Payload $LensStatus -Name 'pilot_indicator'
$ResidentSurface = Get-PropertyValue -Payload $LensStatus -Name 'resident_surface'
$ResidentSurfaceGovernance = Get-PropertyValue -Payload $ResidentSurface -Name 'governance'
$ResidentSurfaceBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $ResidentSurface -Name 'blockers' -Default @()
)
$ResidentSurfaceReadbackReady = (
  [string](Get-PropertyValue -Payload $ResidentSurface -Name 'kind' -Default '') -eq 'lens.resident_surface.readback' -and
  [string](Get-PropertyValue -Payload $ResidentSurface -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $ResidentSurface -Name 'contract_status' -Default '') -eq 'readback_ready' -and
  [string](Get-PropertyValue -Payload $ResidentSurface -Name 'route' -Default '') -eq '/lens/resident-surface' -and
  [bool](Get-PropertyValue -Payload $ResidentSurface -Name 'content_contract_ready' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurface -Name 'resident_surface_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurface -Name 'resident_claim_allowed' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurface -Name 'resident_overlay_runtime' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'resident_claim_authority' -Default $true)
)

$SummonStatus = [string](Get-PropertyValue -Payload $SummonCriterion -Name 'status' -Default 'missing')
$SummonBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $SummonCriterion -Name 'blockers' -Default @())
$ModeStatus = [string](Get-PropertyValue -Payload $ModeCriterion -Name 'status' -Default 'missing')
$HudStatus = [string](Get-PropertyValue -Payload $HudCriterion -Name 'status' -Default 'missing')
$HudBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HudCriterion -Name 'blockers' -Default @())
$HostStatus = [string](Get-PropertyValue -Payload $HostCriterion -Name 'status' -Default 'missing')
$HostBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostCriterion -Name 'blockers' -Default @())
$HostSupervisionAuthorityStatus = [string](Get-PropertyValue -Payload $HostSupervisionAuthorityCriterion -Name 'status' -Default 'missing')
$HostSupervisionAuthorityReady = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityCriterion -Name 'ready' -Default $true)
$HostSupervisionAuthorityPreflightReady = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityCriterion -Name 'preflight_ready' -Default $false)
$HostSupervisionAuthorityAuthorityReady = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityCriterion -Name 'authority_ready' -Default $true)
$HostSupervisionAuthorityRequirementsTotal = [int](Get-PropertyValue -Payload $HostSupervisionAuthorityCriterion -Name 'requirements_total' -Default 0)
$HostSupervisionAuthorityRequirementsReadyTotal = [int](Get-PropertyValue -Payload $HostSupervisionAuthorityCriterion -Name 'requirements_ready_total' -Default 0)
$HostSupervisionAuthorityRequirementsBlockedTotal = [int](Get-PropertyValue -Payload $HostSupervisionAuthorityCriterion -Name 'requirements_blocked_total' -Default 0)
$HostSupervisionAuthorityBlockedRequirements = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostSupervisionAuthorityCriterion -Name 'blocked_requirements' -Default @())
$HostSupervisionAuthorityEvidence = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostSupervisionAuthorityCriterion -Name 'evidence' -Default @())
$HostSupervisionAuthorityBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostSupervisionAuthorityCriterion -Name 'blockers' -Default @())
$HostSupervisionAuthorityObserved = (
  $HostSupervisionAuthorityStatus -eq 'blocked' -and
  $HostSupervisionAuthorityPreflightReady -and
  -not $HostSupervisionAuthorityReady -and
  -not $HostSupervisionAuthorityAuthorityReady -and
  $HostSupervisionAuthorityEvidence -contains '/lens/host/supervision/authority' -and
  $HostSupervisionAuthorityBlockedRequirements -contains 'process_supervision_authority' -and
  $HostSupervisionAuthorityBlockers -contains 'resident_host_supervision_authority_not_granted'
)
$HostSupervisionAuthorityDenialStatus = [string](Get-PropertyValue -Payload $HostSupervisionAuthorityDenialCriterion -Name 'status' -Default 'missing')
$HostSupervisionAuthorityDenialBoundaryReady = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityDenialCriterion -Name 'boundary_ready' -Default $false)
$HostSupervisionAuthorityDenialApplied = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityDenialCriterion -Name 'applied' -Default $true)
$HostSupervisionAuthorityDenialExecuted = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityDenialCriterion -Name 'executed' -Default $true)
$HostSupervisionAuthorityDenialAuthorityGranted = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityDenialCriterion -Name 'authority_granted' -Default $true)
$HostSupervisionAuthorityDenialReady = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityDenialCriterion -Name 'ready' -Default $true)
$HostSupervisionAuthorityDenialAuthorityReady = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityDenialCriterion -Name 'authority_ready' -Default $true)
$HostSupervisionAuthorityDenialEvidence = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostSupervisionAuthorityDenialCriterion -Name 'evidence' -Default @())
$HostSupervisionAuthorityDenialBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostSupervisionAuthorityDenialCriterion -Name 'blockers' -Default @())
$HostSupervisionAuthorityDenialObserved = (
  $HostSupervisionAuthorityDenialStatus -ne 'missing' -and
  $HostSupervisionAuthorityDenialBoundaryReady -and
  -not $HostSupervisionAuthorityDenialApplied -and
  -not $HostSupervisionAuthorityDenialExecuted -and
  -not $HostSupervisionAuthorityDenialAuthorityGranted -and
  -not $HostSupervisionAuthorityDenialReady -and
  -not $HostSupervisionAuthorityDenialAuthorityReady -and
  $HostSupervisionAuthorityDenialEvidence -contains '/lens/host/supervision/authority' -and
  $HostSupervisionAuthorityDenialBlockers -contains 'approval_id_required' -and
  $HostSupervisionAuthorityDenialBlockers -contains 'process_supervision_authority_not_granted'
)
$HostSupervisionAuthorityDenialReceiptsStatus = [string](Get-PropertyValue -Payload $HostSupervisionAuthorityDenialReceiptsCriterion -Name 'status' -Default 'missing')
$HostSupervisionAuthorityDenialReceiptsCount = [int](Get-PropertyValue -Payload $HostSupervisionAuthorityDenialReceiptsCriterion -Name 'receipt_count' -Default 0)
$HostSupervisionAuthorityDenialReceiptsLatestId = [string](Get-PropertyValue -Payload $HostSupervisionAuthorityDenialReceiptsCriterion -Name 'latest_receipt_id' -Default '')
$HostSupervisionAuthorityDenialReceiptsEvidence = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostSupervisionAuthorityDenialReceiptsCriterion -Name 'evidence' -Default @())
$HostSupervisionAuthorityDenialReceiptsObserved = (
  ($HostSupervisionAuthorityDenialReceiptsStatus -eq 'empty' -or $HostSupervisionAuthorityDenialReceiptsStatus -eq 'readback_ready') -and
  $HostSupervisionAuthorityDenialReceiptsEvidence -contains '/lens/host/supervision/authority/denials'
)
$HostSupervisionAuthorityGrantReceiptsStatus = [string](Get-PropertyValue -Payload $HostSupervisionAuthorityGrantReceiptsCriterion -Name 'status' -Default 'missing')
$HostSupervisionAuthorityGrantReceiptsCount = [int](Get-PropertyValue -Payload $HostSupervisionAuthorityGrantReceiptsCriterion -Name 'receipt_count' -Default 0)
$HostSupervisionAuthorityGrantReceiptsLatestId = [string](Get-PropertyValue -Payload $HostSupervisionAuthorityGrantReceiptsCriterion -Name 'latest_receipt_id' -Default '')
$HostSupervisionAuthorityGrantReceiptsActiveId = [string](Get-PropertyValue -Payload $HostSupervisionAuthorityGrantReceiptsCriterion -Name 'active_receipt_id' -Default '')
$HostSupervisionAuthorityGrantReceiptsAuthorityGranted = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityGrantReceiptsCriterion -Name 'authority_granted' -Default $false)
$HostSupervisionAuthorityGrantReceiptsEvidence = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostSupervisionAuthorityGrantReceiptsCriterion -Name 'evidence' -Default @())
$HostSupervisionAuthorityGrantReceiptsObserved = (
  ($HostSupervisionAuthorityGrantReceiptsStatus -eq 'empty' -or $HostSupervisionAuthorityGrantReceiptsStatus -eq 'readback_ready') -and
  $HostSupervisionAuthorityGrantReceiptsEvidence -contains '/lens/host/supervision/authority/grants'
)
$HostSupervisionAuthorityReadinessStatus = [string](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'status' -Default 'missing')
$HostSupervisionAuthorityReadinessAuditStatus = [string](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'audit_status' -Default 'missing')
$HostSupervisionAuthorityReadinessReady = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'ready' -Default $true)
$HostSupervisionAuthorityReadinessPreflightReady = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'preflight_ready' -Default $false)
$HostSupervisionAuthorityReadinessAuthorityReady = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'authority_ready' -Default $true)
$HostSupervisionAuthorityReadinessSupervisionReady = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'supervision_ready' -Default $true)
$HostSupervisionAuthorityReadinessResidentClaimAllowed = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'resident_claim_allowed' -Default $true)
$HostSupervisionAuthorityReadinessBoundaryObserved = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'boundary_observed' -Default $false)
$HostSupervisionAuthorityReadinessDenialReceiptReadbackReady = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'denial_receipt_readback_ready' -Default $false)
$HostSupervisionAuthorityReadinessGrantReceiptReadbackReady = [bool](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'grant_receipt_readback_ready' -Default $false)
$HostSupervisionAuthorityReadinessReceiptCount = [int](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'receipt_count' -Default 0)
$HostSupervisionAuthorityReadinessLatestReceiptId = [string](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'latest_receipt_id' -Default '')
$HostSupervisionAuthorityReadinessGrantReceiptCount = [int](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'grant_receipt_count' -Default 0)
$HostSupervisionAuthorityReadinessLatestGrantReceiptId = [string](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'latest_grant_receipt_id' -Default '')
$HostSupervisionAuthorityReadinessActiveGrantReceiptId = [string](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'active_grant_receipt_id' -Default '')
$HostSupervisionAuthorityReadinessRequirementsTotal = [int](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'requirements_total' -Default 0)
$HostSupervisionAuthorityReadinessRequirementsReadyTotal = [int](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'requirements_ready_total' -Default 0)
$HostSupervisionAuthorityReadinessRequirementsBlockedTotal = [int](Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'requirements_blocked_total' -Default 0)
$HostSupervisionAuthorityReadinessBlockedRequirements = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'blocked_requirements' -Default @())
$HostSupervisionAuthorityReadinessEvidence = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'evidence' -Default @())
$HostSupervisionAuthorityReadinessBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostSupervisionAuthorityReadinessCriterion -Name 'blockers' -Default @())
$HostSupervisionAuthorityReadinessObserved = (
  $HostSupervisionAuthorityReadinessStatus -ne 'missing' -and
  $HostSupervisionAuthorityReadinessAuditStatus -eq 'complete' -and
  -not $HostSupervisionAuthorityReadinessReady -and
  $HostSupervisionAuthorityReadinessPreflightReady -and
  -not $HostSupervisionAuthorityReadinessAuthorityReady -and
  -not $HostSupervisionAuthorityReadinessSupervisionReady -and
  -not $HostSupervisionAuthorityReadinessResidentClaimAllowed -and
  $HostSupervisionAuthorityReadinessBoundaryObserved -and
  $HostSupervisionAuthorityReadinessDenialReceiptReadbackReady -and
  $HostSupervisionAuthorityReadinessGrantReceiptReadbackReady -and
  $HostSupervisionAuthorityReadinessEvidence -contains '/lens/host/supervision/authority/readiness' -and
  $HostSupervisionAuthorityReadinessEvidence -contains '/lens/host/supervision/authority/grants' -and
  $HostSupervisionAuthorityReadinessBlockedRequirements -notcontains 'authority_grant_implementation' -and
  $HostSupervisionAuthorityReadinessBlockedRequirements -contains 'process_supervision_authority' -and
  $HostSupervisionAuthorityReadinessBlockers -notcontains 'host_supervision_authority_grant_not_implemented' -and
  $HostSupervisionAuthorityReadinessBlockers -contains 'process_supervision_authority_not_granted'
)
$PersistentSupervisionEnablementDenialStatus = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementDenialCriterion -Name 'status' -Default 'missing')
$PersistentSupervisionEnablementDenialBoundaryReady = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementDenialCriterion -Name 'boundary_ready' -Default $false)
$PersistentSupervisionEnablementDenialApplied = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementDenialCriterion -Name 'applied' -Default $true)
$PersistentSupervisionEnablementDenialExecuted = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementDenialCriterion -Name 'executed' -Default $true)
$PersistentSupervisionEnablementDenialAuthorityGranted = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementDenialCriterion -Name 'authority_granted' -Default $true)
$PersistentSupervisionEnablementDenialEnablementReady = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementDenialCriterion -Name 'enablement_ready' -Default $true)
$PersistentSupervisionEnablementDenialResidentClaimAllowed = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementDenialCriterion -Name 'resident_claim_allowed' -Default $true)
$PersistentSupervisionEnablementDenialServiceConfigUpdated = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementDenialCriterion -Name 'service_config_updated' -Default $true)
$PersistentSupervisionEnablementDenialAuthorityGrantActive = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementDenialCriterion -Name 'authority_grant_active' -Default $true)
$PersistentSupervisionEnablementDenialEvidence = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $PersistentSupervisionEnablementDenialCriterion -Name 'evidence' -Default @())
$PersistentSupervisionEnablementDenialBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $PersistentSupervisionEnablementDenialCriterion -Name 'blockers' -Default @())
$PersistentSupervisionEnablementDenialObserved = (
  $PersistentSupervisionEnablementDenialStatus -ne 'missing' -and
  $PersistentSupervisionEnablementDenialBoundaryReady -and
  -not $PersistentSupervisionEnablementDenialApplied -and
  -not $PersistentSupervisionEnablementDenialExecuted -and
  -not $PersistentSupervisionEnablementDenialAuthorityGranted -and
  -not $PersistentSupervisionEnablementDenialEnablementReady -and
  -not $PersistentSupervisionEnablementDenialResidentClaimAllowed -and
  -not $PersistentSupervisionEnablementDenialServiceConfigUpdated -and
  -not $PersistentSupervisionEnablementDenialAuthorityGrantActive -and
  $PersistentSupervisionEnablementDenialEvidence -contains '/lens/host/persistent-supervision/enablement' -and
  $PersistentSupervisionEnablementDenialEvidence -contains '/lens/host/persistent-supervision' -and
  $PersistentSupervisionEnablementDenialBlockers -contains 'host_supervision_authority_grant_not_active' -and
  $PersistentSupervisionEnablementDenialBlockers -contains 'persistent_supervision_enablement_authority_not_granted' -and
  $PersistentSupervisionEnablementDenialBlockers -contains 'service_config_write_authority_not_granted'
)
$PersistentSupervisionEnablementExecutionDenialStatus = [string](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionDenialCriterion -Name 'status' -Default 'missing')
$PersistentSupervisionEnablementExecutionDenialBoundaryReady = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionDenialCriterion -Name 'boundary_ready' -Default $false)
$PersistentSupervisionEnablementExecutionDenialApplied = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionDenialCriterion -Name 'applied' -Default $true)
$PersistentSupervisionEnablementExecutionDenialExecuted = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionDenialCriterion -Name 'executed' -Default $true)
$PersistentSupervisionEnablementExecutionDenialReady = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionDenialCriterion -Name 'ready' -Default $true)
$PersistentSupervisionEnablementExecutionDenialApprovalReady = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionDenialCriterion -Name 'approval_ready' -Default $true)
$PersistentSupervisionEnablementExecutionDenialEnablementAuthorityGranted = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionDenialCriterion -Name 'enablement_authority_granted' -Default $true)
$PersistentSupervisionEnablementExecutionDenialEnablementAllowed = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionDenialCriterion -Name 'persistent_supervision_enablement_allowed' -Default $true)
$PersistentSupervisionEnablementExecutionDenialServiceConfigUpdated = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionDenialCriterion -Name 'service_config_updated' -Default $true)
$PersistentSupervisionEnablementExecutionDenialResidentClaimAllowed = [bool](Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionDenialCriterion -Name 'resident_claim_allowed' -Default $true)
$PersistentSupervisionEnablementExecutionDenialEvidence = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionDenialCriterion -Name 'evidence' -Default @())
$PersistentSupervisionEnablementExecutionDenialBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $PersistentSupervisionEnablementExecutionDenialCriterion -Name 'blockers' -Default @())
$PersistentSupervisionEnablementExecutionDenialObserved = (
  $PersistentSupervisionEnablementExecutionDenialStatus -ne 'missing' -and
  $PersistentSupervisionEnablementExecutionDenialBoundaryReady -and
  -not $PersistentSupervisionEnablementExecutionDenialApplied -and
  -not $PersistentSupervisionEnablementExecutionDenialExecuted -and
  -not $PersistentSupervisionEnablementExecutionDenialReady -and
  -not $PersistentSupervisionEnablementExecutionDenialApprovalReady -and
  -not $PersistentSupervisionEnablementExecutionDenialEnablementAuthorityGranted -and
  -not $PersistentSupervisionEnablementExecutionDenialEnablementAllowed -and
  -not $PersistentSupervisionEnablementExecutionDenialServiceConfigUpdated -and
  -not $PersistentSupervisionEnablementExecutionDenialResidentClaimAllowed -and
  $PersistentSupervisionEnablementExecutionDenialEvidence -contains '/lens/host/persistent-supervision/enablement/execution' -and
  $PersistentSupervisionEnablementExecutionDenialEvidence -contains '/lens/host/persistent-supervision/enablement/execution/readiness' -and
  $PersistentSupervisionEnablementExecutionDenialBlockers -contains 'approval_id_required' -and
  $PersistentSupervisionEnablementExecutionDenialBlockers -contains 'persistent_supervision_enablement_authority_not_granted' -and
  $PersistentSupervisionEnablementExecutionDenialBlockers -contains 'service_config_write_authority_not_granted' -and
  $PersistentSupervisionEnablementExecutionDenialBlockers -contains 'persistent_supervision_execution_authority_not_granted'
)
$RuntimePlanStatus = [string](Get-PropertyValue -Payload $RuntimePlanCriterion -Name 'status' -Default 'missing')
$RuntimePlanAvailable = [bool](Get-PropertyValue -Payload $RuntimePlanCriterion -Name 'plan_available' -Default $false)
$RuntimePlanRuntimeReady = [bool](Get-PropertyValue -Payload $RuntimePlanCriterion -Name 'runtime_ready' -Default $false)
$RuntimePlanResidentClaimAllowed = [bool](Get-PropertyValue -Payload $RuntimePlanCriterion -Name 'resident_claim_allowed' -Default $false)
$RuntimePlanEvidence = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimePlanCriterion -Name 'evidence' -Default @())
$RuntimePlanBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimePlanCriterion -Name 'blockers' -Default @())
$RuntimeGrantStatus = [string](Get-PropertyValue -Payload $RuntimeGrantCriterion -Name 'status' -Default 'missing')
$RuntimeGrantReady = [bool](Get-PropertyValue -Payload $RuntimeGrantCriterion -Name 'grant_ready' -Default $false)
$RuntimeGrantRuntimeReady = [bool](Get-PropertyValue -Payload $RuntimeGrantCriterion -Name 'runtime_ready' -Default $false)
$RuntimeGrantResidentClaimAllowed = [bool](Get-PropertyValue -Payload $RuntimeGrantCriterion -Name 'resident_claim_allowed' -Default $false)
$RuntimeGrantEvidence = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimeGrantCriterion -Name 'evidence' -Default @())
$RuntimeGrantBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimeGrantCriterion -Name 'blockers' -Default @())
$RuntimeGrantObserved = (
  $RuntimeGrantStatus -ne 'missing' -and
  -not $RuntimeGrantReady -and
  $RuntimeGrantEvidence -contains '/lens/resident-runtime/preflight' -and
  $RuntimeGrantBlockers -contains 'resident_runtime_execution_authority_not_granted'
)
$RuntimePolicyStatus = [string](Get-PropertyValue -Payload $RuntimePolicyCriterion -Name 'status' -Default 'missing')
$RuntimePolicyReady = [bool](Get-PropertyValue -Payload $RuntimePolicyCriterion -Name 'ready' -Default $false)
$RuntimePolicyContractReady = [bool](Get-PropertyValue -Payload $RuntimePolicyCriterion -Name 'policy_contract_ready' -Default $false)
$RuntimePolicyGrantReady = [bool](Get-PropertyValue -Payload $RuntimePolicyCriterion -Name 'grant_ready' -Default $false)
$RuntimePolicyRuntimeReady = [bool](Get-PropertyValue -Payload $RuntimePolicyCriterion -Name 'runtime_ready' -Default $false)
$RuntimePolicyResidentClaimAllowed = [bool](Get-PropertyValue -Payload $RuntimePolicyCriterion -Name 'resident_claim_allowed' -Default $false)
$RuntimePolicyEvidence = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimePolicyCriterion -Name 'evidence' -Default @())
$RuntimePolicyBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimePolicyCriterion -Name 'blockers' -Default @())
$RuntimePolicyObserved = (
  $RuntimePolicyStatus -eq 'readback_ready' -and
  $RuntimePolicyReady -and
  $RuntimePolicyContractReady -and
  -not $RuntimePolicyGrantReady -and
  $RuntimePolicyBlockers -contains 'resident_runtime_execution_authority_not_granted'
)
$RuntimeAuthorityGrantStatus = [string](Get-PropertyValue -Payload $RuntimeAuthorityGrantCriterion -Name 'status' -Default 'missing')
$RuntimeAuthorityGrantBoundaryReady = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantCriterion -Name 'boundary_ready' -Default $false)
$RuntimeAuthorityGrantApplied = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantCriterion -Name 'applied' -Default $true)
$RuntimeAuthorityGrantExecuted = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantCriterion -Name 'executed' -Default $true)
$RuntimeAuthorityGranted = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantCriterion -Name 'authority_granted' -Default $true)
$RuntimeAuthorityGrantReady = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantCriterion -Name 'grant_ready' -Default $true)
$RuntimeAuthorityGrantRuntimeReady = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantCriterion -Name 'runtime_ready' -Default $true)
$RuntimeAuthorityGrantResidentClaimAllowed = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantCriterion -Name 'resident_claim_allowed' -Default $true)
$RuntimeAuthorityGrantEvidence = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimeAuthorityGrantCriterion -Name 'evidence' -Default @())
$RuntimeAuthorityGrantBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimeAuthorityGrantCriterion -Name 'blockers' -Default @())
$RuntimeAuthorityGrantBoundaryObserved = (
  $RuntimeAuthorityGrantStatus -ne 'missing' -and
  $RuntimeAuthorityGrantBoundaryReady -and
  -not $RuntimeAuthorityGrantApplied -and
  -not $RuntimeAuthorityGrantExecuted -and
  -not $RuntimeAuthorityGranted -and
  -not $RuntimeAuthorityGrantReady -and
  $RuntimeAuthorityGrantEvidence -contains '/lens/resident-runtime/authority-grant' -and
  $RuntimeAuthorityGrantEvidence -contains '/lens/resident-runtime/authority-grant/grants' -and
  $RuntimeAuthorityGrantBlockers -contains 'approval_id_required'
)
$RuntimeAuthorityGrantReceiptsStatus = [string](Get-PropertyValue -Payload $RuntimeAuthorityGrantReceiptsCriterion -Name 'status' -Default 'missing')
$RuntimeAuthorityGrantReceiptsCount = [int](Get-PropertyValue -Payload $RuntimeAuthorityGrantReceiptsCriterion -Name 'receipt_count' -Default 0)
$RuntimeAuthorityGrantReceiptsLatestId = [string](Get-PropertyValue -Payload $RuntimeAuthorityGrantReceiptsCriterion -Name 'latest_receipt_id' -Default '')
$RuntimeAuthorityGrantReceiptsActiveId = [string](Get-PropertyValue -Payload $RuntimeAuthorityGrantReceiptsCriterion -Name 'active_receipt_id' -Default '')
$RuntimeAuthorityGrantReceiptsAuthorityGranted = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantReceiptsCriterion -Name 'authority_granted' -Default $false)
$RuntimeAuthorityGrantReceiptsRuntimeAuthority = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantReceiptsCriterion -Name 'resident_runtime_execution_authority' -Default $false)
$RuntimeAuthorityGrantReceiptsEvidence = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimeAuthorityGrantReceiptsCriterion -Name 'evidence' -Default @())
$RuntimeAuthorityGrantReceiptsObserved = (
  ($RuntimeAuthorityGrantReceiptsStatus -eq 'empty' -or $RuntimeAuthorityGrantReceiptsStatus -eq 'readback_ready') -and
  $RuntimeAuthorityGrantReceiptsEvidence -contains '/lens/resident-runtime/authority-grant/grants'
)
$RuntimeAuthorityGrantDenialReceiptsStatus = [string](Get-PropertyValue -Payload $RuntimeAuthorityGrantDenialReceiptsCriterion -Name 'status' -Default 'missing')
$RuntimeAuthorityGrantDenialReceiptsCount = [int](Get-PropertyValue -Payload $RuntimeAuthorityGrantDenialReceiptsCriterion -Name 'receipt_count' -Default 0)
$RuntimeAuthorityGrantDenialReceiptsLatestId = [string](Get-PropertyValue -Payload $RuntimeAuthorityGrantDenialReceiptsCriterion -Name 'latest_receipt_id' -Default '')
$RuntimeAuthorityGrantDenialReceiptsEvidence = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimeAuthorityGrantDenialReceiptsCriterion -Name 'evidence' -Default @())
$RuntimeAuthorityGrantDenialReceiptsObserved = (
  ($RuntimeAuthorityGrantDenialReceiptsStatus -eq 'empty' -or $RuntimeAuthorityGrantDenialReceiptsStatus -eq 'readback_ready') -and
  $RuntimeAuthorityGrantDenialReceiptsEvidence -contains '/lens/resident-runtime/authority-grant/denials'
)
$RuntimeAuthorityGrantReadinessStatus = [string](Get-PropertyValue -Payload $RuntimeAuthorityGrantReadinessCriterion -Name 'status' -Default 'missing')
$RuntimeAuthorityGrantReadinessAuditStatus = [string](Get-PropertyValue -Payload $RuntimeAuthorityGrantReadinessCriterion -Name 'audit_status' -Default 'missing')
$RuntimeAuthorityGrantReadinessReady = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantReadinessCriterion -Name 'ready' -Default $true)
$RuntimeAuthorityGrantReadinessGrantReady = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantReadinessCriterion -Name 'grant_ready' -Default $true)
$RuntimeAuthorityGrantReadinessRuntimeReady = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantReadinessCriterion -Name 'runtime_ready' -Default $true)
$RuntimeAuthorityGrantReadinessResidentClaimAllowed = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantReadinessCriterion -Name 'resident_claim_allowed' -Default $true)
$RuntimeAuthorityGrantReadinessBoundaryObserved = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantReadinessCriterion -Name 'boundary_observed' -Default $false)
$RuntimeAuthorityGrantReadinessAuthorityGranted = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantReadinessCriterion -Name 'authority_granted' -Default $false)
$RuntimeAuthorityGrantReadinessRuntimeAuthority = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantReadinessCriterion -Name 'resident_runtime_execution_authority' -Default $false)
$RuntimeAuthorityGrantReadinessGrantReceiptReadbackReady = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantReadinessCriterion -Name 'grant_receipt_readback_ready' -Default $false)
$RuntimeAuthorityGrantReadinessDenialReceiptReadbackReady = [bool](Get-PropertyValue -Payload $RuntimeAuthorityGrantReadinessCriterion -Name 'denial_receipt_readback_ready' -Default $false)
$RuntimeAuthorityGrantReadinessRequirementsTotal = [int](Get-PropertyValue -Payload $RuntimeAuthorityGrantReadinessCriterion -Name 'requirements_total' -Default 0)
$RuntimeAuthorityGrantReadinessRequirementsReadyTotal = [int](Get-PropertyValue -Payload $RuntimeAuthorityGrantReadinessCriterion -Name 'requirements_ready_total' -Default 0)
$RuntimeAuthorityGrantReadinessRequirementsBlockedTotal = [int](Get-PropertyValue -Payload $RuntimeAuthorityGrantReadinessCriterion -Name 'requirements_blocked_total' -Default 0)
$RuntimeAuthorityGrantReadinessBlockedRequirements = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimeAuthorityGrantReadinessCriterion -Name 'blocked_requirements' -Default @())
$RuntimeAuthorityGrantReadinessEvidence = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimeAuthorityGrantReadinessCriterion -Name 'evidence' -Default @())
$RuntimeAuthorityGrantReadinessBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimeAuthorityGrantReadinessCriterion -Name 'blockers' -Default @())
$RuntimeAuthorityGrantReadinessObserved = (
  $RuntimeAuthorityGrantReadinessStatus -ne 'missing' -and
  $RuntimeAuthorityGrantReadinessAuditStatus -eq 'complete' -and
  -not $RuntimeAuthorityGrantReadinessReady -and
  -not $RuntimeAuthorityGrantReadinessGrantReady -and
  -not $RuntimeAuthorityGrantReadinessRuntimeReady -and
  -not $RuntimeAuthorityGrantReadinessResidentClaimAllowed -and
  $RuntimeAuthorityGrantReadinessBoundaryObserved -and
  $RuntimeAuthorityGrantReadinessGrantReceiptReadbackReady -and
  $RuntimeAuthorityGrantReadinessDenialReceiptReadbackReady -and
  $RuntimeAuthorityGrantReadinessEvidence -contains '/lens/resident-runtime/authority-grant/readiness' -and
  $RuntimeAuthorityGrantReadinessBlockedRequirements -contains 'resident_runtime_execution_authority' -and
  $RuntimeAuthorityGrantReadinessBlockers -contains 'resident_runtime_execution_authority_not_granted'
)
$RuntimeBoundaryStatus = [string](Get-PropertyValue -Payload $RuntimeBoundaryCriterion -Name 'status' -Default 'missing')
$RuntimeBoundaryApplied = [bool](Get-PropertyValue -Payload $RuntimeBoundaryCriterion -Name 'applied' -Default $true)
$RuntimeBoundaryExecuted = [bool](Get-PropertyValue -Payload $RuntimeBoundaryCriterion -Name 'executed' -Default $true)
$RuntimeBoundaryEvidence = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimeBoundaryCriterion -Name 'evidence' -Default @())
$RuntimeBoundaryBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimeBoundaryCriterion -Name 'blockers' -Default @())
$RuntimeBoundaryObserved = (
  $RuntimeBoundaryStatus -ne 'missing' -and
  -not $RuntimeBoundaryApplied -and
  -not $RuntimeBoundaryExecuted -and
  $RuntimeBoundaryBlockers -contains 'resident_runtime_execution_authority_not_granted'
)
$PilotStatus = [string](Get-PropertyValue -Payload $PilotIndicator -Name 'status' -Default 'missing')

$PowerShellPath = Get-PowerShellPath
$LiveOperatorProofPath = Join-Path $PSScriptRoot 'lens-live-operator-proof.ps1'
$ResidentSurfaceProofPath = Join-Path $PSScriptRoot 'lens-resident-surface-proof.ps1'
$HostLaunchProofPath = Join-Path $PSScriptRoot 'lens-host-launch-proof.ps1'
$HostSupervisorProofPath = Join-Path $PSScriptRoot 'lens-host-supervisor-observation-proof.ps1'
$HostSupervisorOwnedSessionPath = Join-Path $PSScriptRoot 'lens-host-supervisor.ps1'
$ResidentOverlayRuntimeProofPath = Join-Path $PSScriptRoot 'lens-resident-overlay-runtime-proof.ps1'
$ResidentOverlayActivationBoundaryProofPath = Join-Path $PSScriptRoot 'lens-resident-overlay-activation-boundary-proof.ps1'
$ResidentRuntimeGrantedBoundaryProofPath = Join-Path $PSScriptRoot 'lens-resident-runtime-boundary-proof.ps1'
$ResidentRuntimeAuthorityBlockersProofPath = Join-Path $PSScriptRoot 'lens-resident-runtime-authority-blockers-proof.ps1'
$TrayPreflightPath = Join-Path $PSScriptRoot 'lens-tray-preflight.ps1'
$LiveOperatorProofResult = @(Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $LiveOperatorProofPath -ScriptArgs @('-Mode', 'Status'))
$LiveOperatorProof = if ($LiveOperatorProofResult.Count -gt 0) { $LiveOperatorProofResult[-1] } else { $null }
$LiveOperatorExitCode = -1
$LiveOperatorPayload = $null
if ($LiveOperatorProof -is [System.Collections.IDictionary]) {
  if ($LiveOperatorProof.Contains('exit_code') -and $null -ne $LiveOperatorProof['exit_code']) {
    $LiveOperatorExitCode = [int]$LiveOperatorProof['exit_code']
  }
  if ($LiveOperatorProof.Contains('payload') -and $null -ne $LiveOperatorProof['payload']) {
    $LiveOperatorPayload = $LiveOperatorProof['payload']
  }
}
$LiveOperatorProofPassed = (
  $LiveOperatorExitCode -eq 0 -and
  [string](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'kind' -Default '') -eq 'lens.live_operator_experience.proof' -and
  [string](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'operator_experience_proof' -Default $false) -and
  [bool](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'helpful_not_noisy_readback' -Default $false)
)
$LiveOperatorStatus = if ($LiveOperatorProofPassed -and $ResidentSurfaceReadbackReady) {
  'resident_surface_content_readback_ready'
} elseif ($LiveOperatorProofPassed) {
  'operator_readback_proof_ready'
} else {
  'needs_live_operator_proof'
}
$LiveOperatorBlockers = @()
if ($ResidentSurfaceReadbackReady) {
  $LiveOperatorBlockers += 'resident_surface_runtime_missing'
} else {
  $LiveOperatorBlockers += 'resident_surface_readback_missing'
}
if (-not $LiveOperatorProofPassed) {
  $LiveOperatorBlockers += 'operator_experience_proof_missing'
}

$ResidentSurfaceProofResult = @(Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $ResidentSurfaceProofPath -ScriptArgs @('-Mode', 'Status', '-ForegroundRunSeconds', [string]$ResidentSurfaceForegroundRunSeconds))
$ResidentSurfaceProof = if ($ResidentSurfaceProofResult.Count -gt 0) { $ResidentSurfaceProofResult[-1] } else { $null }
$ResidentSurfaceProofExitCode = -1
$ResidentSurfaceProofPayload = $null
if ($ResidentSurfaceProof -is [System.Collections.IDictionary]) {
  if ($ResidentSurfaceProof.Contains('exit_code') -and $null -ne $ResidentSurfaceProof['exit_code']) {
    $ResidentSurfaceProofExitCode = [int]$ResidentSurfaceProof['exit_code']
  }
  if ($ResidentSurfaceProof.Contains('payload') -and $null -ne $ResidentSurfaceProof['payload']) {
    $ResidentSurfaceProofPayload = $ResidentSurfaceProof['payload']
  }
}
$ResidentSurfaceProofDetails = Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'proof'
$ResidentSurfaceForegroundRuntimeBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $ResidentSurfaceProofDetails -Name 'resident_surface_foreground_runtime_blockers' -Default @()
)
$ResidentSurfaceForegroundRuntimeProofPassed = (
  $ResidentSurfaceProofExitCode -eq 0 -and
  [string](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'kind' -Default '') -eq 'lens.resident_surface.readiness_proof' -and
  [string](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'resident_surface_content_readback' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'resident_surface_foreground_runtime_readback' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'resident_surface_foreground_runtime_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'resident_surface_runtime_status' -Default '') -eq 'foreground_runtime_observed' -and
  [bool](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'foreground_host_process_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'foreground_host_runtime_completed' -Default $false) -and
  ($ResidentSurfaceForegroundRuntimeBlockers -contains 'resident_surface_runtime_not_supervised') -and
  ($ResidentSurfaceForegroundRuntimeBlockers -contains 'resident_surface_not_resident') -and
  -not ($ResidentSurfaceForegroundRuntimeBlockers -contains 'resident_surface_runtime_missing') -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'resident_surface_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'resident_claim_allowed' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'resident_host_process' -Default $true)
)
$ResidentSurfaceRuntimeProofBlockers = if ($ResidentSurfaceForegroundRuntimeProofPassed) {
  @(
    @($ResidentSurfaceForegroundRuntimeBlockers | Where-Object {
        $_ -ne 'resident_surface_missing' -and $_ -ne 'resident_surface_runtime_missing'
      }) +
    @('resident_surface_runtime_not_supervised', 'resident_surface_not_resident')
  ) | Sort-Object -Unique
} elseif ($ResidentSurfaceReadbackReady) {
  @('resident_surface_runtime_missing')
} else {
  @('resident_surface_readback_missing')
}
if ($ResidentSurfaceForegroundRuntimeProofPassed) {
  $LiveOperatorStatus = 'resident_surface_foreground_runtime_observed'
  $LiveOperatorBlockers = @(
    @($LiveOperatorBlockers | Where-Object { $_ -ne 'resident_surface_runtime_missing' -and $_ -ne 'resident_surface_readback_missing' }) +
    @($ResidentSurfaceRuntimeProofBlockers)
  ) | Sort-Object -Unique
}

$HostLaunchProofResult = @(Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $HostLaunchProofPath -ScriptArgs @('-Mode', 'Status', '-RunSeconds', [string]$HostLaunchRunSeconds))
$HostLaunchProof = if ($HostLaunchProofResult.Count -gt 0) { $HostLaunchProofResult[-1] } else { $null }
$HostLaunchExitCode = -1
$HostLaunchPayload = $null
if ($HostLaunchProof -is [System.Collections.IDictionary]) {
  if ($HostLaunchProof.Contains('exit_code') -and $null -ne $HostLaunchProof['exit_code']) {
    $HostLaunchExitCode = [int]$HostLaunchProof['exit_code']
  }
  if ($HostLaunchProof.Contains('payload') -and $null -ne $HostLaunchProof['payload']) {
    $HostLaunchPayload = $HostLaunchProof['payload']
  }
}
$HostLaunchProofPassed = (
  $HostLaunchExitCode -eq 0 -and
  [string](Get-PropertyValue -Payload $HostLaunchPayload -Name 'kind' -Default '') -eq 'lens.host.launch_readiness_proof' -and
  [string](Get-PropertyValue -Payload $HostLaunchPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $HostLaunchPayload -Name 'bounded_host_launch_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostLaunchPayload -Name 'launch_completed' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $HostLaunchPayload -Name 'ready_for_resident_claim' -Default $true)
)
$HostLaunchProofBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostLaunchPayload -Name 'blockers' -Default @())

$HostSupervisorProofResult = @(Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $HostSupervisorProofPath -ScriptArgs @('-Mode', 'Status', '-RunSeconds', [string]$SupervisorRunSeconds))
$HostSupervisorProof = if ($HostSupervisorProofResult.Count -gt 0) { $HostSupervisorProofResult[-1] } else { $null }
$HostSupervisorExitCode = -1
$HostSupervisorPayload = $null
if ($HostSupervisorProof -is [System.Collections.IDictionary]) {
  if ($HostSupervisorProof.Contains('exit_code') -and $null -ne $HostSupervisorProof['exit_code']) {
    $HostSupervisorExitCode = [int]$HostSupervisorProof['exit_code']
  }
  if ($HostSupervisorProof.Contains('payload') -and $null -ne $HostSupervisorProof['payload']) {
    $HostSupervisorPayload = $HostSupervisorProof['payload']
  }
}
$HostSupervisorProofPassed = (
  $HostSupervisorExitCode -eq 0 -and
  [string](Get-PropertyValue -Payload $HostSupervisorPayload -Name 'kind' -Default '') -eq 'lens.host.supervisor_observation_proof' -and
  [string](Get-PropertyValue -Payload $HostSupervisorPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $HostSupervisorPayload -Name 'bounded_supervisor_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostSupervisorPayload -Name 'supervisor_observed_running_state' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostSupervisorPayload -Name 'supervisor_observed_stopped_state' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisorPayload -Name 'ready_for_resident_claim' -Default $true)
)
$HostSupervisorProofBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostSupervisorPayload -Name 'blockers' -Default @())

$HostSupervisorOwnedSessionRunSeconds = [Math]::Max(3, [Math]::Min($HostLaunchRunSeconds, $SupervisorRunSeconds))
$HostSupervisorOwnedSessionResult = @(Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $HostSupervisorOwnedSessionPath -ScriptArgs @('-Mode', 'SuperviseOnce', '-RunSeconds', [string]$HostSupervisorOwnedSessionRunSeconds))
$HostSupervisorOwnedSessionProof = if ($HostSupervisorOwnedSessionResult.Count -gt 0) { $HostSupervisorOwnedSessionResult[-1] } else { $null }
$HostSupervisorOwnedSessionExitCode = -1
$HostSupervisorOwnedSessionPayload = $null
if ($HostSupervisorOwnedSessionProof -is [System.Collections.IDictionary]) {
  if ($HostSupervisorOwnedSessionProof.Contains('exit_code') -and $null -ne $HostSupervisorOwnedSessionProof['exit_code']) {
    $HostSupervisorOwnedSessionExitCode = [int]$HostSupervisorOwnedSessionProof['exit_code']
  }
  if ($HostSupervisorOwnedSessionProof.Contains('payload') -and $null -ne $HostSupervisorOwnedSessionProof['payload']) {
    $HostSupervisorOwnedSessionPayload = $HostSupervisorOwnedSessionProof['payload']
  }
}
$HostSupervisorOwnedSessionPassed = (
  $HostSupervisorOwnedSessionExitCode -eq 0 -and
  [string](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'kind' -Default '') -eq 'lens.host.supervisor_runner' -and
  [string](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'status' -Default '') -eq 'supervised_session_completed' -and
  [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'supervisor_started_process' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'bounded_supervised_session' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'bounded_supervisor_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'temporary_host_process_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'supervisor_observed_running_state' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'supervisor_observed_stopped_state' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'ready_for_resident_claim' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'resident_host_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'resident_supervised_runtime' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'supervised' -Default $true)
)
$HostSupervisorOwnedSessionBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'blockers' -Default @())

$ResidentOverlayRuntimeProof = Invoke-JsonScriptWithProofRetry -PowerShellPath $PowerShellPath -ScriptPath $ResidentOverlayRuntimeProofPath -ScriptArgs @('-Mode', 'Status', '-SupervisorRunSeconds', [string]$SupervisorRunSeconds) -ExpectedKind 'lens.resident_overlay_runtime.proof'
$ResidentOverlayRuntimeExitCode = -1
$ResidentOverlayRuntimePayload = $null
if ($ResidentOverlayRuntimeProof -is [System.Collections.IDictionary]) {
  if ($ResidentOverlayRuntimeProof.Contains('exit_code') -and $null -ne $ResidentOverlayRuntimeProof['exit_code']) {
    $ResidentOverlayRuntimeExitCode = [int]$ResidentOverlayRuntimeProof['exit_code']
  }
  if ($ResidentOverlayRuntimeProof.Contains('payload') -and $null -ne $ResidentOverlayRuntimeProof['payload']) {
    $ResidentOverlayRuntimePayload = $ResidentOverlayRuntimeProof['payload']
  }
}
$ResidentOverlayRuntimeProofPassed = (
  $ResidentOverlayRuntimeExitCode -eq 0 -and
  [string](Get-PropertyValue -Payload $ResidentOverlayRuntimePayload -Name 'kind' -Default '') -eq 'lens.resident_overlay_runtime.proof' -and
  [string](Get-PropertyValue -Payload $ResidentOverlayRuntimePayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $ResidentOverlayRuntimePayload -Name 'bounded_supervisor_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentOverlayRuntimePayload -Name 'supervisor_observed_running_state' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentOverlayRuntimePayload -Name 'supervisor_observed_stopped_state' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentOverlayRuntimePayload -Name 'resident_overlay_runtime_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentOverlayRuntimePayload -Name 'ready_for_lens_resident_claim' -Default $true)
)
$ResidentOverlayRuntimeBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentOverlayRuntimePayload -Name 'blockers' -Default @())
if ($LiveOperatorProofPassed) {
  $ResidentOverlayRuntimeBlockers = @($ResidentOverlayRuntimeBlockers | Where-Object { $_ -ne 'operator_experience_proof_missing' })
}

$ResidentOverlayActivationBoundaryProof = Invoke-JsonScriptWithProofRetry -PowerShellPath $PowerShellPath -ScriptPath $ResidentOverlayActivationBoundaryProofPath -ScriptArgs @('-Mode', 'Status', '-StartupTimeoutSeconds', [string]$StartupTimeoutSeconds, '-SupervisorRunSeconds', [string]$SupervisorRunSeconds) -ExpectedKind 'lens.resident_overlay_activation_boundary.proof'
$ResidentOverlayActivationBoundaryExitCode = -1
$ResidentOverlayActivationBoundaryPayload = $null
if ($ResidentOverlayActivationBoundaryProof -is [System.Collections.IDictionary]) {
  if ($ResidentOverlayActivationBoundaryProof.Contains('exit_code') -and $null -ne $ResidentOverlayActivationBoundaryProof['exit_code']) {
    $ResidentOverlayActivationBoundaryExitCode = [int]$ResidentOverlayActivationBoundaryProof['exit_code']
  }
  if ($ResidentOverlayActivationBoundaryProof.Contains('payload') -and $null -ne $ResidentOverlayActivationBoundaryProof['payload']) {
    $ResidentOverlayActivationBoundaryPayload = $ResidentOverlayActivationBoundaryProof['payload']
  }
}
$ResidentOverlayActivationBoundaryProofPassed = (
  $ResidentOverlayActivationBoundaryExitCode -eq 0 -and
  [string](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'kind' -Default '') -eq 'lens.resident_overlay_activation_boundary.proof' -and
  [string](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'live_operator_experience_proof' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'resident_overlay_boundary_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'activation_boundary_observed' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'resident_overlay_activation_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'activation_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'execution_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'executed' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'applied' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'would_launch_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'would_install_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'would_register_hotkey' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'would_open_overlay' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'would_write_memory' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'would_decide_approval' -Default $true)
)
$ResidentOverlayActivationBoundaryBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'blockers' -Default @())
if ($LiveOperatorProofPassed) {
  $ResidentOverlayActivationBoundaryBlockers = @($ResidentOverlayActivationBoundaryBlockers | Where-Object { $_ -ne 'operator_experience_proof_missing' -and $_ -ne 'live_operator_experience_proof_missing' })
}

$ResidentRuntimeGrantedBoundaryProof = Invoke-JsonScriptWithProofRetry -PowerShellPath $PowerShellPath -ScriptPath $ResidentRuntimeGrantedBoundaryProofPath -ScriptArgs @('-Mode', 'Status') -ExpectedKind 'lens.resident_runtime.granted_boundary_proof'
$ResidentRuntimeGrantedBoundaryExitCode = -1
$ResidentRuntimeGrantedBoundaryPayload = $null
if ($ResidentRuntimeGrantedBoundaryProof -is [System.Collections.IDictionary]) {
  if ($ResidentRuntimeGrantedBoundaryProof.Contains('exit_code') -and $null -ne $ResidentRuntimeGrantedBoundaryProof['exit_code']) {
    $ResidentRuntimeGrantedBoundaryExitCode = [int]$ResidentRuntimeGrantedBoundaryProof['exit_code']
  }
  if ($ResidentRuntimeGrantedBoundaryProof.Contains('payload') -and $null -ne $ResidentRuntimeGrantedBoundaryProof['payload']) {
    $ResidentRuntimeGrantedBoundaryPayload = $ResidentRuntimeGrantedBoundaryProof['payload']
  }
}
$ResidentRuntimeGrantedBoundaryBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'blockers' -Default @())
$ResidentRuntimeGrantedBoundaryProofPassed = (
  $ResidentRuntimeGrantedBoundaryExitCode -eq 0 -and
  [string](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'kind' -Default '') -eq 'lens.resident_runtime.granted_boundary_proof' -and
  [string](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'resident_runtime_execution_authority' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'runtime_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'resident_claim_allowed' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'applied' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'executed' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_launch_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_supervise_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_register_tray' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_register_hotkey' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_open_overlay' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_write_memory' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_claim_resident' -Default $true) -and
  -not ($ResidentRuntimeGrantedBoundaryBlockers -contains 'resident_runtime_execution_authority_not_granted') -and
  $ResidentRuntimeGrantedBoundaryBlockers -contains 'process_supervision_authority_not_granted' -and
  $ResidentRuntimeGrantedBoundaryBlockers -contains 'service_control_authority_not_granted' -and
  $ResidentRuntimeGrantedBoundaryBlockers -contains 'tray_registration_authority_not_granted' -and
  $ResidentRuntimeGrantedBoundaryBlockers -contains 'hotkey_registration_authority_not_granted' -and
  $ResidentRuntimeGrantedBoundaryBlockers -contains 'overlay_control_authority_not_granted' -and
  $ResidentRuntimeGrantedBoundaryBlockers -contains 'resident_claim_authority_not_granted'
)

$ResidentRuntimeAuthorityBlockersProof = Invoke-JsonScriptWithProofRetry -PowerShellPath $PowerShellPath -ScriptPath $ResidentRuntimeAuthorityBlockersProofPath -ScriptArgs @('-Mode', 'Status') -ExpectedKind 'lens.resident_runtime.authority_blockers_proof'
$ResidentRuntimeAuthorityBlockersExitCode = -1
$ResidentRuntimeAuthorityBlockersPayload = $null
if ($ResidentRuntimeAuthorityBlockersProof -is [System.Collections.IDictionary]) {
  if ($ResidentRuntimeAuthorityBlockersProof.Contains('exit_code') -and $null -ne $ResidentRuntimeAuthorityBlockersProof['exit_code']) {
    $ResidentRuntimeAuthorityBlockersExitCode = [int]$ResidentRuntimeAuthorityBlockersProof['exit_code']
  }
  if ($ResidentRuntimeAuthorityBlockersProof.Contains('payload') -and $null -ne $ResidentRuntimeAuthorityBlockersProof['payload']) {
    $ResidentRuntimeAuthorityBlockersPayload = $ResidentRuntimeAuthorityBlockersProof['payload']
  }
}
$ResidentRuntimeAuthorityBlockerFamilies = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersPayload -Name 'remaining_authority_families' -Default @())
$ResidentRuntimeAuthorityBlockersSummary = Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersPayload -Name 'summary'
$ResidentRuntimeAuthorityBlockersProofPassed = (
  $ResidentRuntimeAuthorityBlockersExitCode -eq 0 -and
  [string](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersPayload -Name 'kind' -Default '') -eq 'lens.resident_runtime.authority_blockers_proof' -and
  [string](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersSummary -Name 'combined_gap_split' -Default $false) -and
  [int](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersSummary -Name 'blocked_authority_family_total' -Default 0) -eq 6 -and
  $ResidentRuntimeAuthorityBlockerFamilies -contains 'process_supervision' -and
  $ResidentRuntimeAuthorityBlockerFamilies -contains 'service_control' -and
  $ResidentRuntimeAuthorityBlockerFamilies -contains 'tray_presence' -and
  $ResidentRuntimeAuthorityBlockerFamilies -contains 'hotkey_summon' -and
  $ResidentRuntimeAuthorityBlockerFamilies -contains 'overlay_window' -and
  $ResidentRuntimeAuthorityBlockerFamilies -contains 'resident_claim' -and
  [string](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_runtime_process_supervision_authority_boundary'
)

$ResidentRuntimeAuthorityBlockerGroups = Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersPayload -Name 'authority_blocker_groups'
$ResidentRuntimeProcessSupervisionBoundaryGroup = Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockerGroups -Name 'process_supervision'
$ResidentRuntimeProcessSupervisionBoundaryBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $ResidentRuntimeProcessSupervisionBoundaryGroup -Name 'blockers' -Default @()
)
$ResidentRuntimeProcessSupervisionBoundaryRequiredBefore = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $ResidentRuntimeProcessSupervisionBoundaryGroup -Name 'required_before' -Default @()
)
$ResidentRuntimeAuthorityBlockersGovernance = Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersPayload -Name 'governance'
$ResidentRuntimeAuthorityBlockersBoundaryProof = Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersPayload -Name 'boundary_proof'
$ResidentRuntimeProcessSupervisionBoundaryExitCode = if ($ResidentRuntimeAuthorityBlockersProofPassed) { 0 } else { 1 }
$ResidentRuntimeProcessSupervisionBoundaryProofPassed = (
  $ResidentRuntimeAuthorityBlockersProofPassed -and
  [string](Get-PropertyValue -Payload $ResidentRuntimeProcessSupervisionBoundaryGroup -Name 'id' -Default '') -eq 'process_supervision' -and
  [string](Get-PropertyValue -Payload $ResidentRuntimeProcessSupervisionBoundaryGroup -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeProcessSupervisionBoundaryGroup -Name 'ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeProcessSupervisionBoundaryGroup -Name 'authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeProcessSupervisionBoundaryGroup -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_launch_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_supervise_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_register_tray' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_register_hotkey' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_open_overlay' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_write_memory' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_claim_resident' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersGovernance -Name 'process_supervision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersGovernance -Name 'process_restart_authority' -Default $true) -and
  $ResidentRuntimeProcessSupervisionBoundaryBlockers -contains 'local_process_launch_authority_not_granted' -and
  $ResidentRuntimeProcessSupervisionBoundaryBlockers -contains 'process_supervision_authority_not_granted' -and
  $ResidentRuntimeProcessSupervisionBoundaryBlockers -contains 'process_restart_authority_not_granted'
)
$ResidentRuntimeServiceControlBoundaryGroup = Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockerGroups -Name 'service_control'
$ResidentRuntimeServiceControlBoundaryBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $ResidentRuntimeServiceControlBoundaryGroup -Name 'blockers' -Default @()
)
$ResidentRuntimeServiceControlBoundaryRequiredBefore = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $ResidentRuntimeServiceControlBoundaryGroup -Name 'required_before' -Default @()
)
$ResidentRuntimeServiceControlRemainingFamilies = [string[]]@(
  $ResidentRuntimeAuthorityBlockerFamilies | Where-Object { $_ -ne 'process_supervision' -and $_ -ne 'service_control' }
)
$ResidentRuntimeServiceControlBoundaryExitCode = if ($ResidentRuntimeAuthorityBlockersProofPassed -and $ResidentRuntimeProcessSupervisionBoundaryProofPassed) { 0 } else { 1 }
$ResidentRuntimeServiceControlBoundaryProofPassed = (
  $ResidentRuntimeProcessSupervisionBoundaryProofPassed -and
  [string](Get-PropertyValue -Payload $ResidentRuntimeServiceControlBoundaryGroup -Name 'id' -Default '') -eq 'service_control' -and
  [string](Get-PropertyValue -Payload $ResidentRuntimeServiceControlBoundaryGroup -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeServiceControlBoundaryGroup -Name 'ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeServiceControlBoundaryGroup -Name 'authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeServiceControlBoundaryGroup -Name 'would_execute' -Default $true) -and
  [string](Get-PropertyValue -Payload $ResidentRuntimeServiceControlBoundaryGroup -Name 'route' -Default '') -eq '/lens/host/persistent-supervision/enablement' -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersGovernance -Name 'service_install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersGovernance -Name 'service_control_authority' -Default $true) -and
  $ResidentRuntimeServiceControlBoundaryBlockers -contains 'service_install_authority_not_granted' -and
  $ResidentRuntimeServiceControlBoundaryBlockers -contains 'service_control_authority_not_granted'
)
$TrayPreflightResult = @(Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $TrayPreflightPath -ScriptArgs @('-Mode', 'Status'))
$TrayPreflightProof = if ($TrayPreflightResult.Count -gt 0) { $TrayPreflightResult[-1] } else { $null }
$TrayPreflightExitCode = -1
$TrayPreflightPayload = $null
if ($TrayPreflightProof -is [System.Collections.IDictionary]) {
  if ($TrayPreflightProof.Contains('exit_code') -and $null -ne $TrayPreflightProof['exit_code']) {
    $TrayPreflightExitCode = [int]$TrayPreflightProof['exit_code']
  }
  if ($TrayPreflightProof.Contains('payload') -and $null -ne $TrayPreflightProof['payload']) {
    $TrayPreflightPayload = $TrayPreflightProof['payload']
  }
}
$TrayPreflightBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $TrayPreflightPayload -Name 'blockers' -Default @()
)
$TrayPreflightRequiredBeforeEnable = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $TrayPreflightPayload -Name 'required_before_enable' -Default @()
)
$TrayPreflightGovernance = Get-PropertyValue -Payload $TrayPreflightPayload -Name 'governance'
$TrayPreflightObserved = (
  $TrayPreflightExitCode -eq 0 -and
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
$ResidentRuntimeTrayPresenceBoundaryGroup = Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockerGroups -Name 'tray_presence'
$ResidentRuntimeTrayPresenceBoundaryBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $ResidentRuntimeTrayPresenceBoundaryGroup -Name 'blockers' -Default @()
)
$ResidentRuntimeTrayPresenceBoundaryRequiredBefore = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $ResidentRuntimeTrayPresenceBoundaryGroup -Name 'required_before' -Default @()
)
$ResidentRuntimeTrayPresenceRemainingFamilies = [string[]]@(
  $ResidentRuntimeAuthorityBlockerFamilies | Where-Object {
    $_ -ne 'process_supervision' -and $_ -ne 'service_control' -and $_ -ne 'tray_presence'
  }
)
$ResidentRuntimeTrayPresenceBoundaryExitCode = if ($ResidentRuntimeServiceControlBoundaryProofPassed -and $TrayPreflightObserved) { 0 } else { 1 }
$ResidentRuntimeTrayPresenceBoundaryProofPassed = (
  $ResidentRuntimeServiceControlBoundaryProofPassed -and
  $TrayPreflightObserved -and
  [string](Get-PropertyValue -Payload $ResidentRuntimeTrayPresenceBoundaryGroup -Name 'id' -Default '') -eq 'tray_presence' -and
  [string](Get-PropertyValue -Payload $ResidentRuntimeTrayPresenceBoundaryGroup -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeTrayPresenceBoundaryGroup -Name 'ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeTrayPresenceBoundaryGroup -Name 'authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeTrayPresenceBoundaryGroup -Name 'would_execute' -Default $true) -and
  [string](Get-PropertyValue -Payload $ResidentRuntimeTrayPresenceBoundaryGroup -Name 'route' -Default '') -eq '/lens/tray' -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_register_tray' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersGovernance -Name 'tray_registration_authority' -Default $true) -and
  $ResidentRuntimeTrayPresenceBoundaryBlockers -contains 'tray_registration_authority_not_granted' -and
  $ResidentRuntimeTrayPresenceBoundaryBlockers -contains 'tray_icon_authority_not_granted' -and
  $ResidentRuntimeTrayPresenceBoundaryBlockers -contains 'notification_authority_not_granted'
)

$SystemResidentBlockers = @($HostBlockers + $HudBlockers + $HostSupervisionAuthorityBlockers + $HostSupervisionAuthorityReadinessBlockers + $RuntimePlanBlockers + $RuntimeGrantBlockers + $RuntimePolicyBlockers + $RuntimeAuthorityGrantBlockers + $RuntimeAuthorityGrantReadinessBlockers + $RuntimeBoundaryBlockers + $HostSupervisorProofBlockers + $HostSupervisorOwnedSessionBlockers + $ResidentOverlayRuntimeBlockers + $ResidentOverlayActivationBoundaryBlockers | Sort-Object -Unique)
if ($ResidentSurfaceReadbackReady) {
  $SystemResidentBlockers = @(
    @($SystemResidentBlockers | Where-Object {
        $_ -ne 'resident_surface_missing' -and (
          -not $ResidentSurfaceForegroundRuntimeProofPassed -or $_ -ne 'resident_surface_runtime_missing'
        )
      }) +
    @($ResidentSurfaceRuntimeProofBlockers)
  ) | Sort-Object -Unique
} else {
  $SystemResidentBlockers = @($SystemResidentBlockers + @('resident_surface_readback_missing')) | Sort-Object -Unique
}
if ($HostLaunchProofPassed -or $HostSupervisorProofPassed -or $HostSupervisorOwnedSessionPassed) {
  $SystemResidentBlockers = @(
    @($SystemResidentBlockers | Where-Object { $_ -ne 'resident_host_process_missing' }) +
    @('resident_host_process_not_supervised')
  ) | Sort-Object -Unique
}
$SystemResidentStatus = if ($HostStatus -eq 'ready') {
  'ready'
} elseif ($ResidentOverlayActivationBoundaryProofPassed) {
  'resident_overlay_activation_boundary_observed'
} elseif ($ResidentOverlayRuntimeProofPassed) {
  'resident_overlay_boundary_observed'
} elseif ($HostSupervisorOwnedSessionPassed) {
  'bounded_supervisor_owned_session_observed'
} elseif ($HostSupervisorProofPassed) {
  'bounded_supervisor_observed'
} elseif ($HostLaunchProofPassed) {
  'bounded_host_launch_observed'
} else {
  $HostStatus
}

$Criteria = @(
  (New-Criterion `
      -Id 'summon_anywhere' `
      -Label 'The user can summon Francis anywhere' `
      -Status $SummonStatus `
      -Ready ($SummonStatus -eq 'ready') `
      -Evidence @('/lens/status', '/lens/preflight', 'scripts/lens-summon-preflight.ps1') `
      -Blockers $SummonBlockers `
      -Basis 'Roadmap Stage 6 done criterion')
  (New-Criterion `
      -Id 'helpful_not_noisy' `
      -Label 'Lens is helpful, not noisy' `
      -Status $LiveOperatorStatus `
      -Ready $false `
      -Evidence @('/lens/status', '/lens/resident-surface', 'chat_ui.system_orb', 'scripts/lens-live-operator-proof.ps1') `
      -Blockers $LiveOperatorBlockers `
      -Basis 'Live HTTP Lens readback and direct resident-surface content readback exist; resident runtime still blocks a finished Lens claim.')
  (New-Criterion `
      -Id 'mode_visibility' `
      -Label 'Mode visibility becomes real' `
      -Status $ModeStatus `
      -Ready ($ModeStatus -eq 'readback_ready') `
      -Evidence @('/system/operator_mode', '/lens/status') `
      -Blockers @() `
      -Basis 'Mode readback is projected through Lens status.')
  (New-Criterion `
      -Id 'pilot_visibility_groundwork' `
      -Label 'Pilot visibility groundwork is obvious' `
      -Status $(if ($PilotStatus -eq 'missing') { 'missing' } else { 'readback_ready' }) `
      -Ready ($PilotStatus -ne 'missing') `
      -Evidence @('/lens/status', '/system/operator_mode') `
      -Blockers @() `
      -Basis 'Pilot indicator readback exists; live takeover remains outside Stage 6 closure unless separately implemented.')
  (New-Criterion `
      -Id 'system_resident_presence' `
      -Label 'Francis begins to feel system-resident, not tab-trapped' `
      -Status $SystemResidentStatus `
      -Ready ($HostStatus -eq 'ready') `
      -Evidence @('/lens/host', '/lens/preflight', '/lens/resident-surface', '/lens/resident-runtime/preflight', '/lens/resident-runtime/policy', '/lens/resident-runtime/authority-grant', '/lens/resident-runtime/plan', '/lens/resident-runtime/execute', '/lens/resident-surface/activation', 'scripts/lens-host.ps1', 'scripts/lens-host-foreground-proof.ps1', 'scripts/lens-host-launch-proof.ps1', 'scripts/lens-host-supervisor.ps1', 'scripts/lens-host-supervisor-observation-proof.ps1', 'scripts/lens-host-supervision-proof.ps1', 'scripts/lens-resident-surface-proof.ps1', 'scripts/lens-resident-overlay-runtime-proof.ps1', 'scripts/lens-resident-overlay-activation-boundary-proof.ps1') `
      -Blockers $SystemResidentBlockers `
      -Basis $(if ($ResidentOverlayActivationBoundaryProofPassed) { 'Resident overlay activation boundary proof composes live Lens readback, resident overlay boundary observation, and blocked activation readback; resident supervision and real overlay activation remain blocked.' } elseif ($ResidentOverlayRuntimeProofPassed) { 'Resident overlay runtime boundary proof composes one bounded supervisor observation with blocked overlay, tray, hotkey, and summon preflights; resident supervision and real overlay runtime remain blocked.' } elseif ($HostSupervisorOwnedSessionPassed) { 'Bounded supervisor-owned session starts and observes one diagnostic host process through running and stopped states; persistent resident supervision, tray, hotkey, and overlay runtime remain blocked.' } elseif ($HostSupervisorProofPassed) { 'Bounded supervisor observation sees one diagnostic host process through running and stopped states; resident supervision, tray, hotkey, and overlay runtime remain blocked.' } elseif ($HostLaunchProofPassed) { 'Bounded host launch is observable and self-stopping; resident supervision, tray, hotkey, and overlay runtime remain blocked.' } else { 'Resident host, tray, hotkey, and overlay runtime remain blocked.' }))
)

$EnablementGateIds = @(
  'resident_supervision_enablement_gate',
  'summon_enablement_gate',
  'tray_enablement_gate',
  'overlay_enablement_gate'
)
$EnablementGates = @($EnablementGateIds | ForEach-Object {
    $GateId = $_
    $Gate = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId $GateId
    [ordered]@{
      id = $GateId
      status = [string](Get-PropertyValue -Payload $Gate -Name 'status' -Default 'missing')
      ready = [bool](Get-PropertyValue -Payload $Gate -Name 'ready' -Default $false)
      evidence = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Gate -Name 'evidence' -Default @())
      blockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Gate -Name 'blockers' -Default @())
      resident_claim_allowed = [bool](Get-PropertyValue -Payload $Gate -Name 'resident_claim_allowed' -Default $false)
      summon_anywhere = [bool](Get-PropertyValue -Payload $Gate -Name 'summon_anywhere' -Default $false)
      tray_presence = [bool](Get-PropertyValue -Payload $Gate -Name 'tray_presence' -Default $false)
      overlay_window = [bool](Get-PropertyValue -Payload $Gate -Name 'overlay_window' -Default $false)
      global_hotkey = [string](Get-PropertyValue -Payload $Gate -Name 'global_hotkey' -Default '')
      presence_name = [string](Get-PropertyValue -Payload $Gate -Name 'presence_name' -Default '')
      overlay_name = [string](Get-PropertyValue -Payload $Gate -Name 'overlay_name' -Default '')
    }
  })
$ReadyCriteria = @($Criteria | Where-Object { [bool]$_['ready'] })
$BlockedCriteria = @($Criteria | Where-Object { -not [bool]$_['ready'] })
$ReadyEnablementGates = @($EnablementGates | Where-Object { [bool]$_['ready'] })
$BlockedEnablementGates = @($EnablementGates | Where-Object { -not [bool]$_['ready'] })
$AllBlockers = @($Criteria | ForEach-Object { $_['blockers'] } | ForEach-Object { $_ } | Sort-Object -Unique)
$ReadyToClose = $LensStatusOk -and $BlockedCriteria.Count -eq 0
$RuntimeGrantBaseObserved = (
  $LiveOperatorProofPassed -and
  $ResidentOverlayActivationBoundaryProofPassed -and
  $RuntimePlanAvailable -and
  $RuntimeBoundaryObserved -and
  $RuntimeGrantObserved
)
$RuntimeGrantPolicyObserved = $RuntimeGrantBaseObserved -and $RuntimePolicyObserved
$RuntimeGrantBoundarySpineObserved = $RuntimeGrantPolicyObserved -and $RuntimeAuthorityGrantBoundaryObserved
$RuntimeGrantReceiptSpineObserved = $RuntimeGrantBoundarySpineObserved -and $RuntimeAuthorityGrantReceiptsObserved
$RuntimeGrantDenialReceiptSpineObserved = $RuntimeGrantReceiptSpineObserved -and $RuntimeAuthorityGrantDenialReceiptsObserved
$RuntimeGrantReadinessSpineObserved = $RuntimeGrantDenialReceiptSpineObserved -and $RuntimeAuthorityGrantReadinessObserved

$Payload = [ordered]@{
  ok = $true
  kind = 'lens.stage6.checkpoint'
  status = if ($ReadyToClose) { 'ready_to_close' } else { 'blocked' }
  mode = $Mode.ToLowerInvariant()
  stage = 'Stage 6 / Lens MVP'
  stage_state = if ($ReadyToClose) { 'audit_ready' } else { 'active' }
  stage_claim = $StageClaim
  repo_root = $RepoRoot
  ready_to_close = $ReadyToClose
  summary = [ordered]@{
    criteria_total = $Criteria.Count
    ready_total = $ReadyCriteria.Count
    blocked_total = $BlockedCriteria.Count
    enablement_gate_total = $EnablementGates.Count
    enablement_gate_ready_total = $ReadyEnablementGates.Count
    enablement_gate_blocked_total = $BlockedEnablementGates.Count
    blocker_total = $AllBlockers.Count
  }
  criteria = @($Criteria)
  enablement_gates = @($EnablementGates)
  blockers = @($AllBlockers)
  resident_host_supervision_authority_preflight = [ordered]@{
    status = $HostSupervisionAuthorityStatus
    ok = $HostSupervisionAuthorityObserved
    evidence = $HostSupervisionAuthorityEvidence
    ready = $HostSupervisionAuthorityReady
    preflight_ready = $HostSupervisionAuthorityPreflightReady
    authority_ready = $HostSupervisionAuthorityAuthorityReady
    requirements_total = $HostSupervisionAuthorityRequirementsTotal
    requirements_ready_total = $HostSupervisionAuthorityRequirementsReadyTotal
    requirements_blocked_total = $HostSupervisionAuthorityRequirementsBlockedTotal
    blocked_requirements = $HostSupervisionAuthorityBlockedRequirements
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    blockers = $HostSupervisionAuthorityBlockers
  }
  resident_host_supervision_authority_denial_boundary = [ordered]@{
    status = $HostSupervisionAuthorityDenialStatus
    ok = $HostSupervisionAuthorityDenialObserved
    evidence = $HostSupervisionAuthorityDenialEvidence
    boundary_ready = $HostSupervisionAuthorityDenialBoundaryReady
    applied = $HostSupervisionAuthorityDenialApplied
    executed = $HostSupervisionAuthorityDenialExecuted
    authority_granted = $HostSupervisionAuthorityDenialAuthorityGranted
    ready = $HostSupervisionAuthorityDenialReady
    authority_ready = $HostSupervisionAuthorityDenialAuthorityReady
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    denial_receipt_write_authority = $false
    resident_claim_authority = $false
    blockers = $HostSupervisionAuthorityDenialBlockers
  }
  resident_host_supervision_authority_denial_receipts = [ordered]@{
    status = $HostSupervisionAuthorityDenialReceiptsStatus
    ok = $HostSupervisionAuthorityDenialReceiptsObserved
    evidence = $HostSupervisionAuthorityDenialReceiptsEvidence
    receipt_count = $HostSupervisionAuthorityDenialReceiptsCount
    latest_receipt_id = $HostSupervisionAuthorityDenialReceiptsLatestId
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    denial_receipt_write_authority = $false
    resident_claim_authority = $false
  }
  resident_host_supervision_authority_grant_receipts = [ordered]@{
    status = $HostSupervisionAuthorityGrantReceiptsStatus
    ok = $HostSupervisionAuthorityGrantReceiptsObserved
    evidence = $HostSupervisionAuthorityGrantReceiptsEvidence
    receipt_count = $HostSupervisionAuthorityGrantReceiptsCount
    latest_receipt_id = $HostSupervisionAuthorityGrantReceiptsLatestId
    active_receipt_id = $HostSupervisionAuthorityGrantReceiptsActiveId
    authority_granted = $HostSupervisionAuthorityGrantReceiptsAuthorityGranted
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    denial_receipt_write_authority = $false
    resident_claim_authority = $false
  }
  resident_host_supervision_authority_readiness_audit = [ordered]@{
    status = $HostSupervisionAuthorityReadinessStatus
    audit_status = $HostSupervisionAuthorityReadinessAuditStatus
    ok = $HostSupervisionAuthorityReadinessObserved
    evidence = $HostSupervisionAuthorityReadinessEvidence
    ready = $HostSupervisionAuthorityReadinessReady
    preflight_ready = $HostSupervisionAuthorityReadinessPreflightReady
    authority_ready = $HostSupervisionAuthorityReadinessAuthorityReady
    supervision_ready = $HostSupervisionAuthorityReadinessSupervisionReady
    resident_claim_allowed = $HostSupervisionAuthorityReadinessResidentClaimAllowed
    boundary_observed = $HostSupervisionAuthorityReadinessBoundaryObserved
    denial_receipt_readback_ready = $HostSupervisionAuthorityReadinessDenialReceiptReadbackReady
    grant_receipt_readback_ready = $HostSupervisionAuthorityReadinessGrantReceiptReadbackReady
    receipt_count = $HostSupervisionAuthorityReadinessReceiptCount
    latest_receipt_id = $HostSupervisionAuthorityReadinessLatestReceiptId
    grant_receipt_count = $HostSupervisionAuthorityReadinessGrantReceiptCount
    latest_grant_receipt_id = $HostSupervisionAuthorityReadinessLatestGrantReceiptId
    active_grant_receipt_id = $HostSupervisionAuthorityReadinessActiveGrantReceiptId
    requirements_total = $HostSupervisionAuthorityReadinessRequirementsTotal
    requirements_ready_total = $HostSupervisionAuthorityReadinessRequirementsReadyTotal
    requirements_blocked_total = $HostSupervisionAuthorityReadinessRequirementsBlockedTotal
    blocked_requirements = $HostSupervisionAuthorityReadinessBlockedRequirements
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    denial_receipt_write_authority = $false
    resident_claim_authority = $false
    blockers = $HostSupervisionAuthorityReadinessBlockers
  }
  persistent_supervision_enablement_denial_boundary = [ordered]@{
    status = $PersistentSupervisionEnablementDenialStatus
    ok = $PersistentSupervisionEnablementDenialObserved
    evidence = $PersistentSupervisionEnablementDenialEvidence
    boundary_ready = $PersistentSupervisionEnablementDenialBoundaryReady
    applied = $PersistentSupervisionEnablementDenialApplied
    executed = $PersistentSupervisionEnablementDenialExecuted
    authority_granted = $PersistentSupervisionEnablementDenialAuthorityGranted
    enablement_ready = $PersistentSupervisionEnablementDenialEnablementReady
    resident_claim_allowed = $PersistentSupervisionEnablementDenialResidentClaimAllowed
    service_config_updated = $PersistentSupervisionEnablementDenialServiceConfigUpdated
    authority_grant_active = $PersistentSupervisionEnablementDenialAuthorityGrantActive
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_config_write_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    denial_receipt_write_authority = $false
    resident_claim_authority = $false
    blockers = $PersistentSupervisionEnablementDenialBlockers
  }
  persistent_supervision_enablement_execution_denial_boundary = [ordered]@{
    status = $PersistentSupervisionEnablementExecutionDenialStatus
    ok = $PersistentSupervisionEnablementExecutionDenialObserved
    evidence = $PersistentSupervisionEnablementExecutionDenialEvidence
    boundary_ready = $PersistentSupervisionEnablementExecutionDenialBoundaryReady
    applied = $PersistentSupervisionEnablementExecutionDenialApplied
    executed = $PersistentSupervisionEnablementExecutionDenialExecuted
    ready = $PersistentSupervisionEnablementExecutionDenialReady
    approval_ready = $PersistentSupervisionEnablementExecutionDenialApprovalReady
    enablement_authority_granted = $PersistentSupervisionEnablementExecutionDenialEnablementAuthorityGranted
    persistent_supervision_enablement_allowed = $PersistentSupervisionEnablementExecutionDenialEnablementAllowed
    service_config_updated = $PersistentSupervisionEnablementExecutionDenialServiceConfigUpdated
    resident_claim_allowed = $PersistentSupervisionEnablementExecutionDenialResidentClaimAllowed
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    persistent_supervision_enablement_authority = $false
    service_config_write_authority = $false
    persistent_supervision_execution_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    denial_receipt_write_authority = $false
    resident_claim_authority = $false
    blockers = $PersistentSupervisionEnablementExecutionDenialBlockers
  }
  resident_runtime_authority_grant_preflight = [ordered]@{
    status = $RuntimeGrantStatus
    ok = $RuntimeGrantObserved
    evidence = $RuntimeGrantEvidence
    ready = $RuntimeGrantReady
    grant_ready = $RuntimeGrantReady
    authority_grant_ready = $RuntimeGrantReady
    runtime_ready = $RuntimeGrantRuntimeReady
    resident_claim_allowed = $RuntimeGrantResidentClaimAllowed
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    blockers = $RuntimeGrantBlockers
  }
  resident_runtime_execution_policy_contract = [ordered]@{
    status = $RuntimePolicyStatus
    ok = $RuntimePolicyObserved
    evidence = $RuntimePolicyEvidence
    ready = $RuntimePolicyReady
    policy_contract_ready = $RuntimePolicyContractReady
    execution_policy_ready = [bool](Get-PropertyValue -Payload $RuntimePolicyCriterion -Name 'execution_policy_ready' -Default $false)
    grant_ready = $RuntimePolicyGrantReady
    authority_grant_ready = $RuntimePolicyGrantReady
    runtime_ready = $RuntimePolicyRuntimeReady
    resident_claim_allowed = $RuntimePolicyResidentClaimAllowed
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    blockers = $RuntimePolicyBlockers
  }
  resident_runtime_execution_authority_grant_boundary = [ordered]@{
    status = $RuntimeAuthorityGrantStatus
    ok = $RuntimeAuthorityGrantBoundaryObserved
    evidence = $RuntimeAuthorityGrantEvidence
    boundary_ready = $RuntimeAuthorityGrantBoundaryReady
    applied = $RuntimeAuthorityGrantApplied
    executed = $RuntimeAuthorityGrantExecuted
    authority_granted = $RuntimeAuthorityGranted
    grant_ready = $RuntimeAuthorityGrantReady
    authority_grant_ready = $RuntimeAuthorityGrantReady
    runtime_ready = $RuntimeAuthorityGrantRuntimeReady
    resident_claim_allowed = $RuntimeAuthorityGrantResidentClaimAllowed
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    blockers = $RuntimeAuthorityGrantBlockers
  }
  resident_runtime_authority_grant_receipts = [ordered]@{
    status = $RuntimeAuthorityGrantReceiptsStatus
    ok = $RuntimeAuthorityGrantReceiptsObserved
    evidence = $RuntimeAuthorityGrantReceiptsEvidence
    receipt_count = $RuntimeAuthorityGrantReceiptsCount
    latest_receipt_id = $RuntimeAuthorityGrantReceiptsLatestId
    active_receipt_id = $RuntimeAuthorityGrantReceiptsActiveId
    authority_granted = $RuntimeAuthorityGrantReceiptsAuthorityGranted
    resident_runtime_execution_authority = $RuntimeAuthorityGrantReceiptsRuntimeAuthority
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    denial_receipt_write_authority = $false
    resident_claim_authority = $false
  }
  resident_runtime_authority_grant_denial_receipts = [ordered]@{
    status = $RuntimeAuthorityGrantDenialReceiptsStatus
    ok = $RuntimeAuthorityGrantDenialReceiptsObserved
    evidence = $RuntimeAuthorityGrantDenialReceiptsEvidence
    receipt_count = $RuntimeAuthorityGrantDenialReceiptsCount
    latest_receipt_id = $RuntimeAuthorityGrantDenialReceiptsLatestId
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    denial_receipt_write_authority = $false
    resident_claim_authority = $false
  }
  resident_runtime_authority_grant_readiness_audit = [ordered]@{
    status = $RuntimeAuthorityGrantReadinessStatus
    audit_status = $RuntimeAuthorityGrantReadinessAuditStatus
    ok = $RuntimeAuthorityGrantReadinessObserved
    evidence = $RuntimeAuthorityGrantReadinessEvidence
    ready = $RuntimeAuthorityGrantReadinessReady
    grant_ready = $RuntimeAuthorityGrantReadinessGrantReady
    authority_grant_ready = $RuntimeAuthorityGrantReadinessGrantReady
    runtime_ready = $RuntimeAuthorityGrantReadinessRuntimeReady
    resident_claim_allowed = $RuntimeAuthorityGrantReadinessResidentClaimAllowed
    boundary_observed = $RuntimeAuthorityGrantReadinessBoundaryObserved
    authority_granted = $RuntimeAuthorityGrantReadinessAuthorityGranted
    resident_runtime_execution_authority = $RuntimeAuthorityGrantReadinessRuntimeAuthority
    grant_receipt_readback_ready = $RuntimeAuthorityGrantReadinessGrantReceiptReadbackReady
    denial_receipt_readback_ready = $RuntimeAuthorityGrantReadinessDenialReceiptReadbackReady
    requirements_total = $RuntimeAuthorityGrantReadinessRequirementsTotal
    requirements_ready_total = $RuntimeAuthorityGrantReadinessRequirementsReadyTotal
    requirements_blocked_total = $RuntimeAuthorityGrantReadinessRequirementsBlockedTotal
    blocked_requirements = $RuntimeAuthorityGrantReadinessBlockedRequirements
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    denial_receipt_write_authority = $false
    resident_claim_authority = $false
    blockers = $RuntimeAuthorityGrantReadinessBlockers
  }
  resident_runtime_activation_plan = [ordered]@{
    status = $RuntimePlanStatus
    ok = $RuntimePlanStatus -ne 'missing'
    evidence = $RuntimePlanEvidence
    plan_available = $RuntimePlanAvailable
    runtime_ready = $RuntimePlanRuntimeReady
    resident_claim_allowed = $RuntimePlanResidentClaimAllowed
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    blockers = $RuntimePlanBlockers
  }
  resident_runtime_authority_boundary = [ordered]@{
    status = $RuntimeBoundaryStatus
    ok = $RuntimeBoundaryObserved
    evidence = $RuntimeBoundaryEvidence
    applied = $RuntimeBoundaryApplied
    executed = $RuntimeBoundaryExecuted
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    blockers = $RuntimeBoundaryBlockers
  }
  resident_runtime_granted_boundary_proof = [ordered]@{
    status = [string](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'status' -Default 'missing')
    ok = $ResidentRuntimeGrantedBoundaryProofPassed
    exit_code = $ResidentRuntimeGrantedBoundaryExitCode
    evidence = @('scripts/lens-resident-runtime-boundary-proof.ps1', '/lens/resident-runtime/execute', '/lens/resident-runtime/denials')
    resident_runtime_execution_authority = [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'resident_runtime_execution_authority' -Default $false)
    runtime_ready = [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'runtime_ready' -Default $false)
    resident_claim_allowed = [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'resident_claim_allowed' -Default $false)
    applied = [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'applied' -Default $false)
    executed = [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'executed' -Default $false)
    would_launch_process = [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_launch_process' -Default $false)
    would_supervise_process = [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_supervise_process' -Default $false)
    would_restart_process = [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_restart_process' -Default $false)
    would_install_service = [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_install_service' -Default $false)
    would_start_service = [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_start_service' -Default $false)
    would_register_tray = [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_register_tray' -Default $false)
    would_register_hotkey = [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_register_hotkey' -Default $false)
    would_open_overlay = [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_open_overlay' -Default $false)
    would_write_memory = [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_write_memory' -Default $false)
    would_claim_resident = [bool](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'would_claim_resident' -Default $false)
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    blockers = $ResidentRuntimeGrantedBoundaryBlockers
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $ResidentRuntimeGrantedBoundaryPayload -Name 'next_smallest_truthful_gap' -Default '')
  }
  resident_runtime_authority_blockers_proof = [ordered]@{
    status = [string](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersPayload -Name 'status' -Default 'missing')
    ok = $ResidentRuntimeAuthorityBlockersProofPassed
    exit_code = $ResidentRuntimeAuthorityBlockersExitCode
    evidence = @('scripts/lens-resident-runtime-authority-blockers-proof.ps1', 'scripts/lens-resident-runtime-boundary-proof.ps1', '/lens/resident-runtime/execute')
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersPayload -Name 'next_smallest_truthful_gap' -Default '')
    remaining_authority_families = $ResidentRuntimeAuthorityBlockerFamilies
    authority_blocker_groups = Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersPayload -Name 'authority_blocker_groups' -Default ([ordered]@{})
    summary = Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersPayload -Name 'summary' -Default ([ordered]@{})
    governance = Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersPayload -Name 'governance' -Default ([ordered]@{})
  }
  resident_runtime_process_supervision_boundary_proof = [ordered]@{
    status = if ($ResidentRuntimeProcessSupervisionBoundaryProofPassed) { 'proof_passed' } else { 'missing_or_failed' }
    ok = $ResidentRuntimeProcessSupervisionBoundaryProofPassed
    exit_code = $ResidentRuntimeProcessSupervisionBoundaryExitCode
    evidence = @('scripts/lens-resident-runtime-authority-blockers-proof.ps1', '/lens/host/supervision/authority/readiness', '/lens/resident-runtime/execute')
    authority_family = 'process_supervision'
    next_authority_family = 'service_control'
    process_supervision_boundary_observed = $ResidentRuntimeProcessSupervisionBoundaryProofPassed
    authority_blockers_proof_observed = $ResidentRuntimeAuthorityBlockersProofPassed
    side_effects_denied = $ResidentRuntimeProcessSupervisionBoundaryProofPassed
    first_authority_family_consumed = $ResidentRuntimeProcessSupervisionBoundaryProofPassed
    resident_runtime_execution_authority = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersGovernance -Name 'resident_runtime_execution_authority' -Default $false)
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_control_authority = $false
    resident_claim_authority = $false
    would_launch_process = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_launch_process' -Default $false)
    would_supervise_process = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_supervise_process' -Default $false)
    would_restart_process = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_restart_process' -Default $false)
    would_start_service = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_start_service' -Default $false)
    would_register_tray = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_register_tray' -Default $false)
    would_register_hotkey = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_register_hotkey' -Default $false)
    would_open_overlay = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_open_overlay' -Default $false)
    would_write_memory = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_write_memory' -Default $false)
    would_claim_resident = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_claim_resident' -Default $false)
    process_supervision = [ordered]@{
      status = [string](Get-PropertyValue -Payload $ResidentRuntimeProcessSupervisionBoundaryGroup -Name 'status' -Default 'missing')
      ready = [bool](Get-PropertyValue -Payload $ResidentRuntimeProcessSupervisionBoundaryGroup -Name 'ready' -Default $false)
      authority_granted = [bool](Get-PropertyValue -Payload $ResidentRuntimeProcessSupervisionBoundaryGroup -Name 'authority_granted' -Default $false)
      would_execute = [bool](Get-PropertyValue -Payload $ResidentRuntimeProcessSupervisionBoundaryGroup -Name 'would_execute' -Default $false)
      route = [string](Get-PropertyValue -Payload $ResidentRuntimeProcessSupervisionBoundaryGroup -Name 'route' -Default '')
      evidence = [string[]]@(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentRuntimeProcessSupervisionBoundaryGroup -Name 'evidence' -Default @()))
      required_before = [string[]]@($ResidentRuntimeProcessSupervisionBoundaryRequiredBefore)
      blockers = [string[]]@($ResidentRuntimeProcessSupervisionBoundaryBlockers)
    }
    blockers = $ResidentRuntimeProcessSupervisionBoundaryBlockers
    next_smallest_truthful_gap = 'resident_runtime_service_control_authority_boundary'
    governance = [ordered]@{
      diagnostic_only = $true
      wraps_existing_authority_blockers_proof = $true
      approval_request_write = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersGovernance -Name 'approval_request_write' -Default $false)
      resident_runtime_execution_authority = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersGovernance -Name 'resident_runtime_execution_authority' -Default $false)
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
  }
  resident_runtime_service_control_boundary_proof = [ordered]@{
    status = if ($ResidentRuntimeServiceControlBoundaryProofPassed) { 'proof_passed' } else { 'missing_or_failed' }
    ok = $ResidentRuntimeServiceControlBoundaryProofPassed
    exit_code = $ResidentRuntimeServiceControlBoundaryExitCode
    evidence = @('scripts/lens-resident-runtime-authority-blockers-proof.ps1', '/lens/host/persistent-supervision/enablement', '/lens/host/persistent-supervision/enablement/execution/readiness', '/lens/resident-runtime/execute')
    authority_family = 'service_control'
    previous_authority_family = 'process_supervision'
    next_authority_family = 'tray_presence'
    service_control_boundary_observed = $ResidentRuntimeServiceControlBoundaryProofPassed
    previous_process_supervision_family_observed = $ResidentRuntimeProcessSupervisionBoundaryProofPassed
    authority_blockers_proof_observed = $ResidentRuntimeAuthorityBlockersProofPassed
    side_effects_denied = $ResidentRuntimeServiceControlBoundaryProofPassed
    second_authority_family_consumed = $ResidentRuntimeServiceControlBoundaryProofPassed
    resident_runtime_execution_authority = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersGovernance -Name 'resident_runtime_execution_authority' -Default $false)
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    resident_claim_authority = $false
    would_launch_process = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_launch_process' -Default $false)
    would_supervise_process = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_supervise_process' -Default $false)
    would_restart_process = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_restart_process' -Default $false)
    would_install_service = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_install_service' -Default $false)
    would_start_service = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_start_service' -Default $false)
    would_register_tray = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_register_tray' -Default $false)
    would_register_hotkey = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_register_hotkey' -Default $false)
    would_open_overlay = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_open_overlay' -Default $false)
    would_write_memory = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_write_memory' -Default $false)
    would_claim_resident = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_claim_resident' -Default $false)
    service_control = [ordered]@{
      status = [string](Get-PropertyValue -Payload $ResidentRuntimeServiceControlBoundaryGroup -Name 'status' -Default 'missing')
      ready = [bool](Get-PropertyValue -Payload $ResidentRuntimeServiceControlBoundaryGroup -Name 'ready' -Default $false)
      authority_granted = [bool](Get-PropertyValue -Payload $ResidentRuntimeServiceControlBoundaryGroup -Name 'authority_granted' -Default $false)
      would_execute = [bool](Get-PropertyValue -Payload $ResidentRuntimeServiceControlBoundaryGroup -Name 'would_execute' -Default $false)
      route = [string](Get-PropertyValue -Payload $ResidentRuntimeServiceControlBoundaryGroup -Name 'route' -Default '')
      evidence = [string[]]@(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentRuntimeServiceControlBoundaryGroup -Name 'evidence' -Default @()))
      required_before = [string[]]@($ResidentRuntimeServiceControlBoundaryRequiredBefore)
      blockers = [string[]]@($ResidentRuntimeServiceControlBoundaryBlockers)
    }
    blockers = $ResidentRuntimeServiceControlBoundaryBlockers
    remaining_authority_families_after_this_boundary = $ResidentRuntimeServiceControlRemainingFamilies
    next_smallest_truthful_gap = 'resident_runtime_tray_presence_authority_boundary'
    governance = [ordered]@{
      diagnostic_only = $true
      wraps_existing_authority_blockers_proof = $true
      approval_request_write = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersGovernance -Name 'approval_request_write' -Default $false)
      resident_runtime_execution_authority = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersGovernance -Name 'resident_runtime_execution_authority' -Default $false)
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
  }
  resident_runtime_tray_presence_boundary_proof = [ordered]@{
    status = if ($ResidentRuntimeTrayPresenceBoundaryProofPassed) { 'proof_passed' } else { 'missing_or_failed' }
    ok = $ResidentRuntimeTrayPresenceBoundaryProofPassed
    exit_code = $ResidentRuntimeTrayPresenceBoundaryExitCode
    evidence = @('scripts/lens-resident-runtime-authority-blockers-proof.ps1', 'scripts/lens-tray-preflight.ps1', '/lens/tray', '/lens/resident-runtime/execute')
    authority_family = 'tray_presence'
    previous_authority_family = 'service_control'
    next_authority_family = 'hotkey_summon'
    tray_presence_boundary_observed = $ResidentRuntimeTrayPresenceBoundaryProofPassed
    previous_service_control_family_observed = $ResidentRuntimeServiceControlBoundaryProofPassed
    tray_preflight_observed = $TrayPreflightObserved
    authority_blockers_proof_observed = $ResidentRuntimeAuthorityBlockersProofPassed
    side_effects_denied = $ResidentRuntimeTrayPresenceBoundaryProofPassed
    third_authority_family_consumed = $ResidentRuntimeTrayPresenceBoundaryProofPassed
    resident_runtime_execution_authority = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersGovernance -Name 'resident_runtime_execution_authority' -Default $false)
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    tray_registration_authority = $false
    tray_icon_authority = $false
    notification_authority = $false
    resident_claim_authority = $false
    would_launch_process = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_launch_process' -Default $false)
    would_supervise_process = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_supervise_process' -Default $false)
    would_restart_process = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_restart_process' -Default $false)
    would_install_service = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_install_service' -Default $false)
    would_start_service = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_start_service' -Default $false)
    would_register_tray = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_register_tray' -Default $false)
    would_register_hotkey = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_register_hotkey' -Default $false)
    would_open_overlay = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_open_overlay' -Default $false)
    would_write_memory = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_write_memory' -Default $false)
    would_claim_resident = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersBoundaryProof -Name 'would_claim_resident' -Default $false)
    tray_presence = [ordered]@{
      status = [string](Get-PropertyValue -Payload $ResidentRuntimeTrayPresenceBoundaryGroup -Name 'status' -Default 'missing')
      ready = [bool](Get-PropertyValue -Payload $ResidentRuntimeTrayPresenceBoundaryGroup -Name 'ready' -Default $false)
      authority_granted = [bool](Get-PropertyValue -Payload $ResidentRuntimeTrayPresenceBoundaryGroup -Name 'authority_granted' -Default $false)
      would_execute = [bool](Get-PropertyValue -Payload $ResidentRuntimeTrayPresenceBoundaryGroup -Name 'would_execute' -Default $false)
      route = [string](Get-PropertyValue -Payload $ResidentRuntimeTrayPresenceBoundaryGroup -Name 'route' -Default '')
      evidence = [string[]]@(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentRuntimeTrayPresenceBoundaryGroup -Name 'evidence' -Default @()))
      required_before = [string[]]@($ResidentRuntimeTrayPresenceBoundaryRequiredBefore)
      blockers = [string[]]@($ResidentRuntimeTrayPresenceBoundaryBlockers)
    }
    tray_preflight = [ordered]@{
      status = [string](Get-PropertyValue -Payload $TrayPreflightPayload -Name 'status' -Default 'missing')
      ready = [bool](Get-PropertyValue -Payload $TrayPreflightPayload -Name 'ready' -Default $false)
      presence_name = [string](Get-PropertyValue -Payload $TrayPreflightPayload -Name 'presence_name' -Default '')
      config_path = [string](Get-PropertyValue -Payload $TrayPreflightPayload -Name 'config_path' -Default '')
      tray_scope = [string](Get-PropertyValue -Payload $TrayPreflightPayload -Name 'tray_scope' -Default '')
      required_before_enable = [string[]]@($TrayPreflightRequiredBeforeEnable)
      blockers = [string[]]@($TrayPreflightBlockers)
    }
    blockers = $ResidentRuntimeTrayPresenceBoundaryBlockers
    remaining_authority_families_after_this_boundary = $ResidentRuntimeTrayPresenceRemainingFamilies
    next_smallest_truthful_gap = 'resident_runtime_hotkey_summon_authority_boundary'
    governance = [ordered]@{
      diagnostic_only = $true
      wraps_existing_authority_blockers_proof = $true
      tray_preflight_readback = $TrayPreflightObserved
      approval_request_write = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersGovernance -Name 'approval_request_write' -Default $false)
      resident_runtime_execution_authority = [bool](Get-PropertyValue -Payload $ResidentRuntimeAuthorityBlockersGovernance -Name 'resident_runtime_execution_authority' -Default $false)
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
  }
  resident_surface_content_readback = [ordered]@{
    status = [string](Get-PropertyValue -Payload $ResidentSurface -Name 'status' -Default 'missing')
    ok = $ResidentSurfaceReadbackReady
    evidence = @('/lens/resident-surface', '/lens/status')
    route = [string](Get-PropertyValue -Payload $ResidentSurface -Name 'route' -Default '')
    activation_route = [string](Get-PropertyValue -Payload $ResidentSurface -Name 'activation_route' -Default '')
    contract_status = [string](Get-PropertyValue -Payload $ResidentSurface -Name 'contract_status' -Default '')
    content_contract_ready = [bool](Get-PropertyValue -Payload $ResidentSurface -Name 'content_contract_ready' -Default $false)
    resident_surface_ready = [bool](Get-PropertyValue -Payload $ResidentSurface -Name 'resident_surface_ready' -Default $false)
    resident_overlay_runtime = [bool](Get-PropertyValue -Payload $ResidentSurface -Name 'resident_overlay_runtime' -Default $false)
    resident_claim_allowed = [bool](Get-PropertyValue -Payload $ResidentSurface -Name 'resident_claim_allowed' -Default $false)
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $false
    resident_claim_authority = $false
    blockers = @(
      @($ResidentSurfaceBlockers | Where-Object { $_ -ne 'resident_surface_missing' }) +
      @('resident_surface_runtime_missing')
    ) | Sort-Object -Unique
  }
  resident_surface_foreground_runtime_proof = [ordered]@{
    status = [string](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'status' -Default 'missing')
    ok = $ResidentSurfaceForegroundRuntimeProofPassed
    exit_code = $ResidentSurfaceProofExitCode
    evidence = @('/lens/resident-surface?limit=5', 'scripts/lens-resident-surface-proof.ps1')
    resident_surface_content_readback = [bool](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'resident_surface_content_readback' -Default $false)
    resident_surface_foreground_runtime_readback = [bool](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'resident_surface_foreground_runtime_readback' -Default $false)
    resident_surface_foreground_runtime_observed = [bool](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'resident_surface_foreground_runtime_observed' -Default $false)
    resident_surface_runtime_status = [string](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'resident_surface_runtime_status' -Default '')
    foreground_host_process_observed = [bool](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'foreground_host_process_observed' -Default $false)
    foreground_host_runtime_completed = [bool](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'foreground_host_runtime_completed' -Default $false)
    resident_surface_ready = [bool](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'resident_surface_ready' -Default $false)
    resident_claim_allowed = [bool](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'resident_claim_allowed' -Default $false)
    resident_host_process = [bool](Get-PropertyValue -Payload $ResidentSurfaceProofPayload -Name 'resident_host_process' -Default $false)
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $false
    local_process_launch_authority = $true
    process_supervision_authority = $false
    service_control_authority = $false
    resident_claim_authority = $false
    blockers = @($ResidentSurfaceRuntimeProofBlockers)
  }
  live_operator_experience_proof = [ordered]@{
    status = [string](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'status' -Default 'missing')
    ok = $LiveOperatorProofPassed
    exit_code = $LiveOperatorExitCode
    evidence = @('/lens/status?limit=5', 'scripts/lens-live-operator-proof.ps1')
    live_http_status_readback = [bool](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'live_http_status_readback' -Default $false)
    helpful_not_noisy_readback = [bool](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'helpful_not_noisy_readback' -Default $false)
    operator_experience_proof = [bool](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'operator_experience_proof' -Default $false)
    live_operator_experience_ready = [bool](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'live_operator_experience_ready' -Default $false)
    ready_for_stage6_closure = [bool](Get-PropertyValue -Payload $LiveOperatorPayload -Name 'ready_for_stage6_closure' -Default $false)
    blockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $LiveOperatorPayload -Name 'blockers' -Default @())
  }
  host_launch_proof = [ordered]@{
    status = [string](Get-PropertyValue -Payload $HostLaunchPayload -Name 'status' -Default 'missing')
    ok = $HostLaunchProofPassed
    exit_code = $HostLaunchExitCode
    evidence = @('scripts/lens-host.ps1 -Mode Launch', 'scripts/lens-host-launch-proof.ps1')
    bounded_host_launch_observed = [bool](Get-PropertyValue -Payload $HostLaunchPayload -Name 'bounded_host_launch_observed' -Default $false)
    launch_authority_boundary = [bool](Get-PropertyValue -Payload $HostLaunchPayload -Name 'launch_authority_boundary' -Default $false)
    launch_completed = [bool](Get-PropertyValue -Payload $HostLaunchPayload -Name 'launch_completed' -Default $false)
    ready_for_resident_claim = [bool](Get-PropertyValue -Payload $HostLaunchPayload -Name 'ready_for_resident_claim' -Default $false)
    blockers = $HostLaunchProofBlockers
  }
  host_supervisor_observation_proof = [ordered]@{
    status = [string](Get-PropertyValue -Payload $HostSupervisorPayload -Name 'status' -Default 'missing')
    ok = $HostSupervisorProofPassed
    exit_code = $HostSupervisorExitCode
    evidence = @('scripts/lens-host.ps1 -Mode Launch', 'scripts/lens-host-supervisor-observation-proof.ps1')
    bounded_supervisor_observed = [bool](Get-PropertyValue -Payload $HostSupervisorPayload -Name 'bounded_supervisor_observed' -Default $false)
    supervisor_observed_running_state = [bool](Get-PropertyValue -Payload $HostSupervisorPayload -Name 'supervisor_observed_running_state' -Default $false)
    supervisor_observed_stopped_state = [bool](Get-PropertyValue -Payload $HostSupervisorPayload -Name 'supervisor_observed_stopped_state' -Default $false)
    ready_for_resident_claim = [bool](Get-PropertyValue -Payload $HostSupervisorPayload -Name 'ready_for_resident_claim' -Default $false)
    blockers = $HostSupervisorProofBlockers
  }
  host_supervisor_owned_session = [ordered]@{
    status = [string](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'status' -Default 'missing')
    ok = $HostSupervisorOwnedSessionPassed
    exit_code = $HostSupervisorOwnedSessionExitCode
    evidence = @('scripts/lens-host-supervisor.ps1 -Mode SuperviseOnce', 'scripts/lens-host.ps1 -Mode Foreground')
    supervisor_started_process = [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'supervisor_started_process' -Default $false)
    bounded_supervised_session = [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'bounded_supervised_session' -Default $false)
    bounded_supervisor_observed = [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'bounded_supervisor_observed' -Default $false)
    temporary_host_process_observed = [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'temporary_host_process_observed' -Default $false)
    supervisor_observed_running_state = [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'supervisor_observed_running_state' -Default $false)
    supervisor_observed_stopped_state = [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'supervisor_observed_stopped_state' -Default $false)
    ready_for_resident_claim = [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'ready_for_resident_claim' -Default $false)
    resident_host_process = [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'resident_host_process' -Default $false)
    resident_supervised_runtime = [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'resident_supervised_runtime' -Default $false)
    supervised = [bool](Get-PropertyValue -Payload $HostSupervisorOwnedSessionPayload -Name 'supervised' -Default $false)
    local_process_launch_authority = $HostSupervisorOwnedSessionPassed
    api_local_process_launch_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_control_authority = $false
    resident_claim_authority = $false
    blockers = $HostSupervisorOwnedSessionBlockers
  }
  resident_overlay_runtime_proof = [ordered]@{
    status = [string](Get-PropertyValue -Payload $ResidentOverlayRuntimePayload -Name 'status' -Default 'missing')
    ok = $ResidentOverlayRuntimeProofPassed
    exit_code = $ResidentOverlayRuntimeExitCode
    evidence = @('scripts/lens-resident-surface-proof.ps1', 'scripts/lens-host-supervisor-observation-proof.ps1', 'scripts/lens-resident-overlay-runtime-proof.ps1')
    bounded_supervisor_observed = [bool](Get-PropertyValue -Payload $ResidentOverlayRuntimePayload -Name 'bounded_supervisor_observed' -Default $false)
    resident_overlay_runtime_ready = [bool](Get-PropertyValue -Payload $ResidentOverlayRuntimePayload -Name 'resident_overlay_runtime_ready' -Default $false)
    resident_overlay_runtime = [bool](Get-PropertyValue -Payload $ResidentOverlayRuntimePayload -Name 'resident_overlay_runtime' -Default $false)
    overlay_window = [bool](Get-PropertyValue -Payload $ResidentOverlayRuntimePayload -Name 'overlay_window' -Default $false)
    tray_presence = [bool](Get-PropertyValue -Payload $ResidentOverlayRuntimePayload -Name 'tray_presence' -Default $false)
    global_hotkey_bound = [bool](Get-PropertyValue -Payload $ResidentOverlayRuntimePayload -Name 'global_hotkey_bound' -Default $false)
    summon_anywhere = [bool](Get-PropertyValue -Payload $ResidentOverlayRuntimePayload -Name 'summon_anywhere' -Default $false)
    ready_for_lens_resident_claim = [bool](Get-PropertyValue -Payload $ResidentOverlayRuntimePayload -Name 'ready_for_lens_resident_claim' -Default $false)
    blockers = $ResidentOverlayRuntimeBlockers
  }
  resident_overlay_activation_boundary_proof = [ordered]@{
    status = [string](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'status' -Default 'missing')
    ok = $ResidentOverlayActivationBoundaryProofPassed
    exit_code = $ResidentOverlayActivationBoundaryExitCode
    evidence = @('scripts/lens-live-operator-proof.ps1', 'scripts/lens-resident-overlay-runtime-proof.ps1', 'scripts/lens-resident-overlay-activation-boundary-proof.ps1', '/lens/resident-surface/activation')
    live_operator_experience_proof = [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'live_operator_experience_proof' -Default $false)
    resident_overlay_boundary_observed = [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'resident_overlay_boundary_observed' -Default $false)
    activation_boundary_observed = [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'activation_boundary_observed' -Default $false)
    resident_overlay_activation_ready = [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'resident_overlay_activation_ready' -Default $false)
    activation_ready = [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'activation_ready' -Default $false)
    execution_ready = [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'execution_ready' -Default $false)
    executed = [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'executed' -Default $false)
    applied = [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'applied' -Default $false)
    would_launch_process = [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'would_launch_process' -Default $false)
    would_install_service = [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'would_install_service' -Default $false)
    would_start_service = [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'would_start_service' -Default $false)
    would_register_hotkey = [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'would_register_hotkey' -Default $false)
    would_open_overlay = [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'would_open_overlay' -Default $false)
    would_write_memory = [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'would_write_memory' -Default $false)
    would_decide_approval = [bool](Get-PropertyValue -Payload $ResidentOverlayActivationBoundaryPayload -Name 'would_decide_approval' -Default $false)
    blockers = $ResidentOverlayActivationBoundaryBlockers
  }
  next_smallest_truthful_gap = if ($RuntimeGrantReadinessSpineObserved -and $HostSupervisionAuthorityObserved -and $HostSupervisionAuthorityDenialObserved -and $HostSupervisionAuthorityDenialReceiptsObserved -and $HostSupervisionAuthorityGrantReceiptsObserved -and $HostSupervisionAuthorityReadinessObserved -and $PersistentSupervisionEnablementDenialObserved -and $PersistentSupervisionEnablementExecutionDenialObserved) {
    'stage6_lens_completion_audit'
  } elseif ($RuntimeGrantReadinessSpineObserved -and $HostSupervisionAuthorityObserved -and $HostSupervisionAuthorityDenialObserved -and $HostSupervisionAuthorityDenialReceiptsObserved -and $HostSupervisionAuthorityGrantReceiptsObserved -and $HostSupervisionAuthorityReadinessObserved -and $PersistentSupervisionEnablementDenialObserved) {
    'persistent_supervision_enablement_execution_denial_boundary'
  } elseif ($RuntimeGrantReadinessSpineObserved -and $HostSupervisionAuthorityObserved -and $HostSupervisionAuthorityDenialObserved -and $HostSupervisionAuthorityDenialReceiptsObserved -and $HostSupervisionAuthorityGrantReceiptsObserved -and $HostSupervisionAuthorityReadinessObserved) {
    'persistent_supervision_enablement_denial_boundary'
  } elseif ($RuntimeGrantReadinessSpineObserved -and $HostSupervisionAuthorityObserved -and $HostSupervisionAuthorityDenialObserved -and $HostSupervisionAuthorityDenialReceiptsObserved -and $HostSupervisionAuthorityGrantReceiptsObserved) {
    'resident_host_supervision_authority_readiness_audit'
  } elseif ($RuntimeGrantReadinessSpineObserved -and $HostSupervisionAuthorityObserved -and $HostSupervisionAuthorityDenialObserved -and $HostSupervisionAuthorityDenialReceiptsObserved) {
    'resident_host_supervision_authority_grant_receipt_readback'
  } elseif ($RuntimeGrantReadinessSpineObserved -and $HostSupervisionAuthorityObserved -and $HostSupervisionAuthorityDenialObserved) {
    'resident_host_supervision_authority_denial_receipt_readback'
  } elseif ($RuntimeGrantReadinessSpineObserved -and $HostSupervisionAuthorityObserved) {
    'supervised_resident_host_process_supervision_authority_denial_boundary'
  } elseif ($RuntimeGrantReadinessSpineObserved) {
    'resident_host_supervision_authority_preflight'
  } elseif ($RuntimeGrantDenialReceiptSpineObserved) {
    'supervised_resident_host_runtime_authority_grant_readiness_audit'
  } elseif ($RuntimeGrantReceiptSpineObserved) {
    'supervised_resident_host_runtime_execution_authority_grant_denial_receipt_readback'
  } elseif ($RuntimeGrantBoundarySpineObserved) {
    'supervised_resident_host_runtime_execution_authority_grant_receipt_readback'
  } elseif ($RuntimeGrantPolicyObserved) {
    'supervised_resident_host_runtime_execution_authority_grant_boundary'
  } elseif ($RuntimeGrantBaseObserved) {
    'supervised_resident_host_runtime_execution_policy_contract'
  } elseif ($LiveOperatorProofPassed -and $ResidentOverlayActivationBoundaryProofPassed -and $RuntimePlanAvailable -and $RuntimeBoundaryObserved) {
    'supervised_resident_host_runtime_execution_authority_grant'
  } elseif ($LiveOperatorProofPassed -and $ResidentOverlayActivationBoundaryProofPassed -and $RuntimePlanAvailable) {
    'supervised_resident_host_runtime_authority_boundary'
  } elseif ($LiveOperatorProofPassed -and $ResidentOverlayActivationBoundaryProofPassed) {
    'supervised_resident_host_tray_hotkey_overlay_runtime_plan'
  } elseif ($LiveOperatorProofPassed -and $ResidentOverlayRuntimeProofPassed) {
    'resident_overlay_activation_or_process_supervision_authority_boundary'
  } elseif ($LiveOperatorProofPassed -and $HostSupervisorProofPassed) {
    'resident_host_process_supervision_or_resident_overlay_runtime'
  } elseif ($LiveOperatorProofPassed -and $HostLaunchProofPassed) {
    'resident_host_supervision_or_resident_overlay_runtime'
  } elseif ($LiveOperatorProofPassed) {
    'bounded_host_launch_proof'
  } else {
    'live_operator_experience_proof'
  }
  governance = [ordered]@{
    read_only_contract = $true
    diagnostic_only = $true
    live_http_readback = $true
    temporary_api_process = $true
    bounded_host_launch = ($HostLaunchProofPassed -or $HostSupervisorProofPassed -or $ResidentOverlayRuntimeProofPassed -or $ResidentOverlayActivationBoundaryProofPassed)
    bounded_supervisor_observation = ($HostSupervisorProofPassed -or $HostSupervisorOwnedSessionPassed -or $ResidentOverlayRuntimeProofPassed -or $ResidentOverlayActivationBoundaryProofPassed)
    bounded_supervisor_owned_session = $HostSupervisorOwnedSessionPassed
    resident_overlay_boundary_observed = $ResidentOverlayRuntimeProofPassed
    resident_overlay_activation_boundary_observed = $ResidentOverlayActivationBoundaryProofPassed
    resident_surface_foreground_runtime_proof_observed = $ResidentSurfaceForegroundRuntimeProofPassed
    resident_runtime_authority_boundary_observed = $RuntimeBoundaryObserved
    resident_runtime_authority_grant_preflight_observed = $RuntimeGrantObserved
    resident_runtime_execution_policy_contract_observed = $RuntimePolicyObserved
    resident_runtime_execution_authority_grant_boundary_observed = $RuntimeAuthorityGrantBoundaryObserved
    resident_runtime_execution_authority_grant_receipt_readback_observed = $RuntimeAuthorityGrantReceiptsObserved
    resident_runtime_execution_authority_grant_denial_receipt_readback_observed = $RuntimeAuthorityGrantDenialReceiptsObserved
    resident_runtime_execution_authority_grant_readiness_audit_observed = $RuntimeAuthorityGrantReadinessObserved
    resident_runtime_granted_boundary_proof_observed = $ResidentRuntimeGrantedBoundaryProofPassed
    resident_runtime_authority_blockers_proof_observed = $ResidentRuntimeAuthorityBlockersProofPassed
    resident_runtime_process_supervision_boundary_proof_observed = $ResidentRuntimeProcessSupervisionBoundaryProofPassed
    resident_runtime_service_control_boundary_proof_observed = $ResidentRuntimeServiceControlBoundaryProofPassed
    resident_runtime_tray_presence_boundary_proof_observed = $ResidentRuntimeTrayPresenceBoundaryProofPassed
    resident_host_supervision_authority_preflight_observed = $HostSupervisionAuthorityObserved
    resident_host_supervision_authority_denial_boundary_observed = $HostSupervisionAuthorityDenialObserved
    resident_host_supervision_authority_denial_receipt_readback_observed = $HostSupervisionAuthorityDenialReceiptsObserved
    resident_host_supervision_authority_grant_receipt_readback_observed = $HostSupervisionAuthorityGrantReceiptsObserved
    resident_host_supervision_authority_readiness_audit_observed = $HostSupervisionAuthorityReadinessObserved
    persistent_supervision_enablement_denial_boundary_observed = $PersistentSupervisionEnablementDenialObserved
    persistent_supervision_enablement_execution_denial_boundary_observed = $PersistentSupervisionEnablementExecutionDenialObserved
    temporary_runtime_state_write = $true
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    resident_overlay_activation_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = ($ResidentSurfaceForegroundRuntimeProofPassed -or $HostLaunchProofPassed -or $HostSupervisorProofPassed -or $HostSupervisorOwnedSessionPassed -or $ResidentOverlayRuntimeProofPassed -or $ResidentOverlayActivationBoundaryProofPassed)
    api_local_process_launch_authority = $false
    activation_local_process_launch_authority = $false
    process_restart_authority = $false
    process_supervision_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    receipt_write_authority = $false
    denial_receipt_write_authority = $false
    mutation_authority_granted = $false
  }
}

$Payload | ConvertTo-Json -Depth 8
exit 0
