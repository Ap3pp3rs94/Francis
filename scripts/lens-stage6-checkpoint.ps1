[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(5, 60)]
  [int]$StartupTimeoutSeconds = 20,

  [ValidateRange(2, 30)]
  [int]$HostLaunchRunSeconds = 3,

  [ValidateRange(3, 30)]
  [int]$SupervisorRunSeconds = 4
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
$RuntimePlanCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_runtime_activation_plan'
$RuntimeGrantCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_runtime_authority_grant_preflight'
$RuntimePolicyCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_runtime_execution_policy_contract'
$RuntimeBoundaryCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'resident_runtime_authority_boundary'
$PilotIndicator = Get-PropertyValue -Payload $LensStatus -Name 'pilot_indicator'

$SummonStatus = [string](Get-PropertyValue -Payload $SummonCriterion -Name 'status' -Default 'missing')
$SummonBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $SummonCriterion -Name 'blockers' -Default @())
$ModeStatus = [string](Get-PropertyValue -Payload $ModeCriterion -Name 'status' -Default 'missing')
$HudStatus = [string](Get-PropertyValue -Payload $HudCriterion -Name 'status' -Default 'missing')
$HudBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HudCriterion -Name 'blockers' -Default @())
$HostStatus = [string](Get-PropertyValue -Payload $HostCriterion -Name 'status' -Default 'missing')
$HostBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostCriterion -Name 'blockers' -Default @())
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
  $RuntimeGrantBlockers -contains 'resident_runtime_authority_grant_not_implemented'
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
$HostLaunchProofPath = Join-Path $PSScriptRoot 'lens-host-launch-proof.ps1'
$HostSupervisorProofPath = Join-Path $PSScriptRoot 'lens-host-supervisor-observation-proof.ps1'
$ResidentOverlayRuntimeProofPath = Join-Path $PSScriptRoot 'lens-resident-overlay-runtime-proof.ps1'
$ResidentOverlayActivationBoundaryProofPath = Join-Path $PSScriptRoot 'lens-resident-overlay-activation-boundary-proof.ps1'
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
$LiveOperatorStatus = if ($LiveOperatorProofPassed) { 'operator_readback_proof_ready' } else { 'needs_live_operator_proof' }
$LiveOperatorBlockers = if ($LiveOperatorProofPassed) {
  @('resident_surface_missing')
} else {
  @('resident_surface_missing', 'operator_experience_proof_missing')
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

$ResidentOverlayRuntimeProofResult = @(Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $ResidentOverlayRuntimeProofPath -ScriptArgs @('-Mode', 'Status', '-SupervisorRunSeconds', [string]$SupervisorRunSeconds))
$ResidentOverlayRuntimeProof = if ($ResidentOverlayRuntimeProofResult.Count -gt 0) { $ResidentOverlayRuntimeProofResult[-1] } else { $null }
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

$ResidentOverlayActivationBoundaryProofResult = @(Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $ResidentOverlayActivationBoundaryProofPath -ScriptArgs @('-Mode', 'Status', '-StartupTimeoutSeconds', [string]$StartupTimeoutSeconds, '-SupervisorRunSeconds', [string]$SupervisorRunSeconds))
$ResidentOverlayActivationBoundaryProof = if ($ResidentOverlayActivationBoundaryProofResult.Count -gt 0) { $ResidentOverlayActivationBoundaryProofResult[-1] } else { $null }
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

$SystemResidentBlockers = @($HostBlockers + $HudBlockers + $RuntimePlanBlockers + $RuntimeGrantBlockers + $RuntimePolicyBlockers + $RuntimeBoundaryBlockers + $HostSupervisorProofBlockers + $ResidentOverlayRuntimeBlockers + $ResidentOverlayActivationBoundaryBlockers | Sort-Object -Unique)
if ($HostLaunchProofPassed -or $HostSupervisorProofPassed) {
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
      -Evidence @('/lens/status', 'chat_ui.system_orb', 'scripts/lens-live-operator-proof.ps1') `
      -Blockers $LiveOperatorBlockers `
      -Basis 'Live HTTP Lens readback proof exists; resident surface still blocks a finished Lens claim.')
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
      -Evidence @('/lens/host', '/lens/preflight', '/lens/resident-runtime/preflight', '/lens/resident-runtime/policy', '/lens/resident-runtime/plan', '/lens/resident-runtime/execute', '/lens/resident-surface/activation', 'scripts/lens-host.ps1', 'scripts/lens-host-foreground-proof.ps1', 'scripts/lens-host-launch-proof.ps1', 'scripts/lens-host-supervisor-observation-proof.ps1', 'scripts/lens-host-supervision-proof.ps1', 'scripts/lens-resident-surface-proof.ps1', 'scripts/lens-resident-overlay-runtime-proof.ps1', 'scripts/lens-resident-overlay-activation-boundary-proof.ps1') `
      -Blockers $SystemResidentBlockers `
      -Basis $(if ($ResidentOverlayActivationBoundaryProofPassed) { 'Resident overlay activation boundary proof composes live Lens readback, resident overlay boundary observation, and blocked activation readback; resident supervision and real overlay activation remain blocked.' } elseif ($ResidentOverlayRuntimeProofPassed) { 'Resident overlay runtime boundary proof composes one bounded supervisor observation with blocked overlay, tray, hotkey, and summon preflights; resident supervision and real overlay runtime remain blocked.' } elseif ($HostSupervisorProofPassed) { 'Bounded supervisor observation sees one diagnostic host process through running and stopped states; resident supervision, tray, hotkey, and overlay runtime remain blocked.' } elseif ($HostLaunchProofPassed) { 'Bounded host launch is observable and self-stopping; resident supervision, tray, hotkey, and overlay runtime remain blocked.' } else { 'Resident host, tray, hotkey, and overlay runtime remain blocked.' }))
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
  next_smallest_truthful_gap = if ($LiveOperatorProofPassed -and $ResidentOverlayActivationBoundaryProofPassed -and $RuntimePlanAvailable -and $RuntimeBoundaryObserved -and $RuntimeGrantObserved -and $RuntimePolicyObserved) { 'supervised_resident_host_runtime_execution_authority_grant_boundary' } elseif ($LiveOperatorProofPassed -and $ResidentOverlayActivationBoundaryProofPassed -and $RuntimePlanAvailable -and $RuntimeBoundaryObserved -and $RuntimeGrantObserved) { 'supervised_resident_host_runtime_execution_policy_contract' } elseif ($LiveOperatorProofPassed -and $ResidentOverlayActivationBoundaryProofPassed -and $RuntimePlanAvailable -and $RuntimeBoundaryObserved) { 'supervised_resident_host_runtime_execution_authority_grant' } elseif ($LiveOperatorProofPassed -and $ResidentOverlayActivationBoundaryProofPassed -and $RuntimePlanAvailable) { 'supervised_resident_host_runtime_authority_boundary' } elseif ($LiveOperatorProofPassed -and $ResidentOverlayActivationBoundaryProofPassed) { 'supervised_resident_host_tray_hotkey_overlay_runtime_plan' } elseif ($LiveOperatorProofPassed -and $ResidentOverlayRuntimeProofPassed) { 'resident_overlay_activation_or_process_supervision_authority_boundary' } elseif ($LiveOperatorProofPassed -and $HostSupervisorProofPassed) { 'resident_host_process_supervision_or_resident_overlay_runtime' } elseif ($LiveOperatorProofPassed -and $HostLaunchProofPassed) { 'resident_host_supervision_or_resident_overlay_runtime' } elseif ($LiveOperatorProofPassed) { 'bounded_host_launch_proof' } else { 'live_operator_experience_proof' }
  governance = [ordered]@{
    read_only_contract = $true
    diagnostic_only = $true
    live_http_readback = $true
    temporary_api_process = $true
    bounded_host_launch = ($HostLaunchProofPassed -or $HostSupervisorProofPassed)
    bounded_supervisor_observation = $HostSupervisorProofPassed
    resident_overlay_boundary_observed = $ResidentOverlayRuntimeProofPassed
    resident_overlay_activation_boundary_observed = $ResidentOverlayActivationBoundaryProofPassed
    resident_runtime_authority_boundary_observed = $RuntimeBoundaryObserved
    resident_runtime_authority_grant_preflight_observed = $RuntimeGrantObserved
    resident_runtime_execution_policy_contract_observed = $RuntimePolicyObserved
    temporary_runtime_state_write = $true
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    resident_overlay_activation_authority = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = ($HostLaunchProofPassed -or $HostSupervisorProofPassed)
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
