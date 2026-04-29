[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status'
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
$PilotIndicator = Get-PropertyValue -Payload $LensStatus -Name 'pilot_indicator'

$SummonStatus = [string](Get-PropertyValue -Payload $SummonCriterion -Name 'status' -Default 'missing')
$SummonBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $SummonCriterion -Name 'blockers' -Default @())
$ModeStatus = [string](Get-PropertyValue -Payload $ModeCriterion -Name 'status' -Default 'missing')
$HudStatus = [string](Get-PropertyValue -Payload $HudCriterion -Name 'status' -Default 'missing')
$HudBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HudCriterion -Name 'blockers' -Default @())
$HostStatus = [string](Get-PropertyValue -Payload $HostCriterion -Name 'status' -Default 'missing')
$HostBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HostCriterion -Name 'blockers' -Default @())
$PilotStatus = [string](Get-PropertyValue -Payload $PilotIndicator -Name 'status' -Default 'missing')

$PowerShellPath = Get-PowerShellPath
$LiveOperatorProofPath = Join-Path $PSScriptRoot 'lens-live-operator-proof.ps1'
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
      -Status $HostStatus `
      -Ready ($HostStatus -eq 'ready') `
      -Evidence @('/lens/host', '/lens/preflight', '/lens/resident-surface/activation', 'scripts/lens-host.ps1', 'scripts/lens-host-foreground-proof.ps1', 'scripts/lens-host-supervision-proof.ps1', 'scripts/lens-resident-surface-proof.ps1') `
      -Blockers @($HostBlockers + $HudBlockers | Sort-Object -Unique) `
      -Basis 'Resident host, tray, hotkey, and overlay runtime remain blocked.')
)

$ReadyCriteria = @($Criteria | Where-Object { [bool]$_['ready'] })
$BlockedCriteria = @($Criteria | Where-Object { -not [bool]$_['ready'] })
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
    blocker_total = $AllBlockers.Count
  }
  criteria = @($Criteria)
  blockers = @($AllBlockers)
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
  next_smallest_truthful_gap = if ($LiveOperatorProofPassed) { 'resident_host_or_resident_overlay_runtime' } else { 'live_operator_experience_proof' }
  governance = [ordered]@{
    read_only_contract = $true
    diagnostic_only = $true
    live_http_readback = $true
    temporary_api_process = $true
    temporary_runtime_state_write = $true
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    mutation_authority_granted = $false
  }
}

$Payload | ConvertTo-Json -Depth 8
exit 0
