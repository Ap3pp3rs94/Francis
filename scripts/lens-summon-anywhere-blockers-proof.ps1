param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',
  [string]$StatusPath = ''
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

function Invoke-JsonScript {
  param(
    [Parameter(Mandatory = $true)]
    [string]$PowerShellPath,

    [Parameter(Mandatory = $true)]
    [string]$ScriptPath,

    [string[]]$ScriptArgs = @()
  )

  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
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

function Select-Blockers {
  param(
    [string[]]$Blockers,
    [string[]]$Candidates
  )

  return [string[]]@($Candidates | Where-Object { $Blockers -contains $_ })
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

function New-BlockerFamilyHandoff {
  param(
    [string]$Family,
    [string[]]$Blockers
  )

  $MetadataByFamily = @{
    resident_host = [ordered]@{
      label = 'Resident host'
      proof_script = 'scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status'
      route = '/lens/host'
      readiness_route = '/lens/host/runtime-loop/readiness'
      next_step = 'run_resident_host_blocker_proof'
      next_smallest_truthful_gap = 'resident_host_runtime_blocker_boundary'
      authority_required = 'resident_runtime_execution_authority'
    }
    tray_presence = [ordered]@{
      label = 'Tray presence'
      proof_script = 'scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status'
      route = '/lens/tray'
      readiness_route = '/lens/tray/readiness'
      next_step = 'run_tray_presence_blocker_proof'
      next_smallest_truthful_gap = 'summon_overlay_window_blocker_boundary'
      authority_required = 'tray_registration_authority'
    }
    overlay_window = [ordered]@{
      label = 'Overlay window'
      proof_script = 'scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status'
      route = '/lens/overlay'
      readiness_route = '/lens/overlay/readiness'
      next_step = 'run_overlay_window_blocker_proof'
      next_smallest_truthful_gap = 'summon_global_hotkey_binding_blocker_boundary'
      authority_required = 'overlay_control_authority'
    }
    global_hotkey_binding = [ordered]@{
      label = 'Global hotkey binding'
      proof_script = 'scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status'
      route = '/lens/summon'
      readiness_route = '/lens/summon/readiness'
      next_step = 'run_global_hotkey_binding_blocker_proof'
      next_smallest_truthful_gap = 'summon_binding_blocker_boundary'
      authority_required = 'hotkey_registration_authority'
    }
    summon_binding = [ordered]@{
      label = 'Summon binding'
      proof_script = 'scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status'
      route = '/lens/summon'
      readiness_route = '/lens/summon/readiness'
      next_step = 'run_summon_binding_blocker_proof'
      next_smallest_truthful_gap = 'summon_authority_blocker_boundary'
      authority_required = 'summon_authority'
    }
    authority = [ordered]@{
      label = 'Summon authority'
      proof_script = 'scripts/lens-summon-authority-blocker-proof.ps1 -Mode Status'
      route = '/lens/summon'
      readiness_route = '/lens/summon/readiness'
      next_step = 'run_summon_authority_blocker_proof'
      next_smallest_truthful_gap = 'stage6_lens_completion_audit'
      authority_required = 'summon_hotkey_overlay_and_process_authority'
    }
  }

  if (-not $MetadataByFamily.ContainsKey($Family)) {
    return $null
  }

  $Metadata = $MetadataByFamily[$Family]
  return [ordered]@{
    id = $Family
    label = [string]$Metadata.label
    status = if (@($Blockers).Count -gt 0) { 'blocked' } else { 'ready' }
    blockers = [string[]]@($Blockers)
    proof_script = [string]$Metadata.proof_script
    route = [string]$Metadata.route
    readiness_route = [string]$Metadata.readiness_route
    next_step = [string]$Metadata.next_step
    next_smallest_truthful_gap = [string]$Metadata.next_smallest_truthful_gap
    authority_required = [string]$Metadata.authority_required
    authority_granted = $false
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
  }
}

function Get-LensStatus {
  param(
    [string]$StatusPath
  )

  if (-not [string]::IsNullOrWhiteSpace($StatusPath)) {
    try {
      $ResolvedStatusPath = (Resolve-Path -LiteralPath $StatusPath -ErrorAction Stop).Path
      $Payload = Get-Content -LiteralPath $ResolvedStatusPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
      return [ordered]@{
        ok = $true
        source = 'status_path'
        evidence = $ResolvedStatusPath
        payload = $Payload
        error = ''
      }
    } catch {
      return [ordered]@{
        ok = $false
        source = 'status_path'
        evidence = $StatusPath
        payload = $null
        error = [string]$_.Exception.Message
      }
    }
  }

  $Python = Get-Command python -ErrorAction SilentlyContinue
  if ($null -eq $Python) {
    return [ordered]@{
      ok = $false
      source = 'python'
      evidence = 'francis.lens.status.lens_status'
      payload = $null
      error = 'python_unavailable'
    }
  }

  $Source = @'
import json
from francis.lens.status import lens_status
print(json.dumps(lens_status(limit=5)))
'@
  $Output = & $Python.Source -c $Source
  if ($LASTEXITCODE -ne 0) {
    return [ordered]@{
      ok = $false
      source = 'python'
      evidence = 'francis.lens.status.lens_status'
      payload = $null
      error = 'lens_status_failed'
      exit_code = $LASTEXITCODE
      output = ($Output -join "`n")
    }
  }

  try {
    return [ordered]@{
      ok = $true
      source = 'python'
      evidence = 'francis.lens.status.lens_status'
      payload = (($Output -join "`n") | ConvertFrom-Json -ErrorAction Stop)
      error = ''
    }
  } catch {
    return [ordered]@{
      ok = $false
      source = 'python'
      evidence = 'francis.lens.status.lens_status'
      payload = $null
      error = [string]$_.Exception.Message
    }
  }
}

function Get-ReadinessCriterion {
  param(
    [AllowNull()]
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

function Get-ClosureReadinessCriterion {
  param(
    [AllowNull()]
    [object]$Stage6Readiness,
    [string]$CriterionId
  )

  $ClosureReadback = Get-PropertyValue -Payload $Stage6Readiness -Name 'closure_readback'
  $Criteria = Get-PropertyValue -Payload $ClosureReadback -Name 'criteria' -Default @()
  foreach ($Criterion in @($Criteria)) {
    if ((Get-PropertyValue -Payload $Criterion -Name 'id' -Default '') -eq $CriterionId) {
      return $Criterion
    }
  }
  return $null
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$SummonPreflightScript = Join-Path $PSScriptRoot 'lens-summon-preflight.ps1'
if (-not (Test-Path -LiteralPath $SummonPreflightScript -PathType Leaf)) {
  throw "Lens summon preflight script is missing: $SummonPreflightScript"
}

$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction Stop
}

$SummonPreflightResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $SummonPreflightScript -ScriptArgs @('-Mode', 'Status')
$SummonPreflightPayload = $SummonPreflightResult.payload
$SummonPreflightBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPreflightPayload -Name 'blockers' -Default @()
)
$SummonPreflightRequiredBeforeEnable = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPreflightPayload -Name 'required_before_enable' -Default @()
)
$SummonPreflightGovernance = Get-PropertyValue -Payload $SummonPreflightPayload -Name 'governance'
$LensStatusRead = Get-LensStatus -StatusPath $StatusPath
$LensStatus = Get-PropertyValue -Payload $LensStatusRead -Name 'payload'
$Stage6Readiness = Get-PropertyValue -Payload $LensStatus -Name 'stage6_readiness'
$Stage6ClosureReadback = Get-PropertyValue -Payload $Stage6Readiness -Name 'closure_readback'
$SummonAnywhereClosureCriterion = Get-ClosureReadinessCriterion -Stage6Readiness $Stage6Readiness -CriterionId 'summon_anywhere'
$SummonAnywhereClosureHandoff = Get-PropertyValue -Payload $SummonAnywhereClosureCriterion -Name 'handoff' -Default ([ordered]@{})
$FirstBlockerFamilyCompletionAuditHandoff = Get-PropertyValue -Payload $SummonAnywhereClosureHandoff -Name 'first_blocker_family_completion_audit_handoff' -Default ([ordered]@{})
$Stage6PrerequisiteBringupPlan = Get-PropertyValue -Payload $Stage6Readiness -Name 'prerequisite_bringup' -Default ([ordered]@{})
$Stage6PrerequisiteBringupPlanGovernance = Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'governance' -Default ([ordered]@{})
$Stage6PrerequisiteBringupPlanNextOperatorAction = Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_action' -Default ([ordered]@{})
$Stage6PrerequisiteBringupPlanNextOperatorCommand = Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_command' -Default ([ordered]@{})
$Stage6PrerequisiteBringupPlanRequiredBeforeEnable = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'required_before_enable' -Default @()
)
$Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'missing_required_before_enable' -Default @()
)
$Stage6PrerequisiteBringupPlanStatus = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'status' -Default '')
$Stage6PrerequisiteBringupPlanKind = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'kind' -Default '')
$Stage6PrerequisiteBringupPlanPresent = -not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupPlanKind)
$Stage6PrerequisiteBringupPlanCurrentGap = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_truthful_gap' -Default '')
$Stage6PrerequisiteBringupPlanCurrentGapBasis = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_truthful_gap_basis' -Default '')
$Stage6PrerequisiteBringupPlanFirstMissingRequirement = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_first_missing_requirement' -Default '')
$Stage6PrerequisiteBringupPlanFirstMissingTruthfulGap = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'current_first_missing_truthful_gap' -Default '')
$Stage6PrerequisiteBringupPlanNextOperatorRequirement = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'next_operator_action_requirement' -Default '')
$Stage6PrerequisiteBringupPlanRecommendedNextSlice = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'recommended_next_slice' -Default '')
$Stage6PrerequisiteBringupPlanRecommendedProofScript = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'recommended_proof_script' -Default '')
$Stage6PrerequisiteBringupNextOperatorActionId = [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanNextOperatorAction -Name 'id' -Default '')
$Stage6PrerequisiteBringupPlanRequiredBeforeEnableReady = [bool](
  Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'required_before_enable_ready' -Default $false
)
$Stage6PrerequisiteBringupPlanApplied = (
  $Stage6PrerequisiteBringupPlanStatus -eq 'persistent_supervision_enablement_applied' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnableReady -and
  @($Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable).Count -eq 0 -and
  $Stage6PrerequisiteBringupPlanCurrentGap -eq 'persistent_supervision_execution_boundary' -and
  $Stage6PrerequisiteBringupPlanNextOperatorRequirement -eq 'persistent_supervision_enablement_receipt' -and
  $Stage6PrerequisiteBringupNextOperatorActionId -eq 'review_persistent_supervision_enablement_receipt'
)
$Stage6PrerequisiteBringupNeedsOperatorPlanHandoff = -not $Stage6PrerequisiteBringupPlanApplied
$OsBindingAuthorityRequests = Get-PropertyValue -Payload $LensStatus -Name 'os_binding_authority_requests'
$OsBindingAuthorityRequestsGovernance = Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'governance'
$OsBindingReadinessCriterion = Get-ReadinessCriterion -LensStatus $LensStatus -CriterionId 'os_binding_readiness'
$OsBindingReadinessAuthorityRequestReady = [bool](Get-PropertyValue -Payload $OsBindingReadinessCriterion -Name 'authority_request_readback_ready' -Default $false)
$OsBindingReadinessAuthorityRequestsRoute = [string](Get-PropertyValue -Payload $OsBindingReadinessCriterion -Name 'authority_requests_route' -Default '')
$OsBindingReadinessAuthorityRequestRoute = [string](Get-PropertyValue -Payload $OsBindingReadinessCriterion -Name 'authority_request_route' -Default '')
$OsBindingReadinessAuthorityRequestStatus = [string](Get-PropertyValue -Payload $OsBindingReadinessCriterion -Name 'authority_request_readback_status' -Default 'missing')
$OsBindingReadinessEvidence = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $OsBindingReadinessCriterion -Name 'evidence' -Default @()
)

$Stage6BlockerGroups = [ordered]@{
  resident_host = [string[]]@(Select-Blockers -Blockers $SummonPreflightBlockers -Candidates @(
      'lens_host_runtime_not_implemented',
      'lens_host_persistent_supervision_prerequisites_pending',
      'resident_host_process_missing',
      'resident_host_process_not_supervised',
      'local_process_launch_authority_not_granted'
    ))
  tray_presence = [string[]]@(Select-Blockers -Blockers $SummonPreflightBlockers -Candidates @(
      'tray_host_missing'
    ))
  overlay_window = [string[]]@(Select-Blockers -Blockers $SummonPreflightBlockers -Candidates @(
      'overlay_window_missing'
    ))
  global_hotkey_binding = [string[]]@(Select-Blockers -Blockers $SummonPreflightBlockers -Candidates @(
      'global_hotkey_binding_disabled',
      'global_hotkey_registration_disabled',
      'hotkey_registration_authority_not_granted'
    ))
  summon_binding = [string[]]@(Select-Blockers -Blockers $SummonPreflightBlockers -Candidates @(
      'lens_summon_binding_not_implemented',
      'lens_summon_binding_disabled_pending_authority',
      'summon_authority_not_granted'
    ))
  authority = [string[]]@(Select-Blockers -Blockers $SummonPreflightBlockers -Candidates @(
      'summon_authority_not_granted',
      'hotkey_registration_authority_not_granted',
      'overlay_control_authority_not_granted',
      'local_process_launch_authority_not_granted'
    ))
}

$Stage6BlockerFamilyOrder = @(
  'resident_host',
  'tray_presence',
  'overlay_window',
  'global_hotkey_binding',
  'summon_binding',
  'authority'
)
$Stage6BlockedFamilies = [string[]]@(
  $Stage6BlockerFamilyOrder | Where-Object {
    (ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Stage6BlockerGroups -Name $_ -Default @())).Count -gt 0
  }
)

$SummonPreflightObserved = (
  [int]$SummonPreflightResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'kind' -Default '') -eq 'lens.summon.preflight' -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'ready' -Default $true) -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'acceptance_criterion' -Default '') -eq 'summon_anywhere' -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'global_hotkey' -Default '') -ne '' -and
  $SummonPreflightBlockers -contains 'global_hotkey_binding_disabled' -and
  $SummonPreflightBlockers -contains 'global_hotkey_registration_disabled' -and
  $SummonPreflightBlockers -contains 'summon_authority_not_granted' -and
  $SummonPreflightBlockers -contains 'hotkey_registration_authority_not_granted'
)
$Stage6FamilyProjectionObserved = (
  @($Stage6BlockedFamilies).Count -eq 6 -and
  $Stage6BlockedFamilies[0] -eq 'resident_host' -and
  $Stage6BlockedFamilies -contains 'tray_presence' -and
  $Stage6BlockedFamilies -contains 'overlay_window' -and
  $Stage6BlockedFamilies -contains 'global_hotkey_binding' -and
  $Stage6BlockedFamilies -contains 'summon_binding' -and
  $Stage6BlockedFamilies -contains 'authority'
)
$SideEffectsDenied = (
  [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'read_only_contract' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'capture_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'new_sensing_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'mutation_authority_granted' -Default $true)
)
$OsBindingAuthorityRequestReadbackObserved = (
  [bool](Get-PropertyValue -Payload $LensStatusRead -Name 'ok' -Default $false) -and
  [string](Get-PropertyValue -Payload $LensStatus -Name 'kind' -Default '') -eq 'lens.status' -and
  [string](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'kind' -Default '') -eq 'lens.os_binding.command_palette_binding_authority.request_readback' -and
  [string](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'route' -Default '') -eq '/lens/os-binding/authority/requests' -and
  [string](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'authority_route' -Default '') -eq '/lens/os-binding/authority' -and
  [string](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'request_route' -Default '') -eq '/lens/os-binding/authority/request' -and
  [string](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'readiness_route' -Default '') -eq '/lens/os-binding/readiness' -and
  [string](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'plan_route' -Default '') -eq '/lens/os-binding/plan' -and
  $OsBindingReadinessAuthorityRequestReady -and
  [string](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'authority_required' -Default '') -eq 'os_level_command_palette_binding_authority' -and
  $OsBindingReadinessAuthorityRequestsRoute -eq '/lens/os-binding/authority/requests' -and
  $OsBindingReadinessAuthorityRequestRoute -eq '/lens/os-binding/authority/request' -and
  $OsBindingReadinessEvidence -contains '/lens/os-binding/authority/requests' -and
  $OsBindingReadinessEvidence -contains '/lens/os-binding/authority/request' -and
  [string](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'status' -Default '') -in @('none', 'approval_requested', 'approved_no_authority', 'authority_granted') -and
  -not [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'os_level_command_palette' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'summon_anywhere' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'opens_palette' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'registers_hotkey' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'launches_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'controls_overlay' -Default $true) -and
  [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequestsGovernance -Name 'read_only_contract' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequestsGovernance -Name 'approval_request_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequestsGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequestsGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequestsGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequestsGovernance -Name 'resident_claim_authority' -Default $true)
)
$Stage6PrerequisiteBringupPlanObserved = (
  $Stage6PrerequisiteBringupPlanPresent -and
  $Stage6PrerequisiteBringupPlanKind -eq 'lens.stage6.prerequisite_bringup.plan' -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'ok' -Default $false) -and
  [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'stage_state' -Default '') -eq 'active' -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'ready_to_close' -Default $true) -and
  [string](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlan -Name 'acceptance_criterion' -Default '') -eq 'system_resident_presence' -and
  -not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupPlanStatus) -and
  -not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupPlanCurrentGap) -and
  -not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupPlanCurrentGapBasis) -and
  -not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupNextOperatorActionId) -and
  -not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupPlanRecommendedNextSlice) -and
  -not [string]::IsNullOrWhiteSpace($Stage6PrerequisiteBringupPlanRecommendedProofScript) -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'resident_host_process' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'tray_presence' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'global_hotkey_binding' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'overlay_window' -and
  $Stage6PrerequisiteBringupPlanRequiredBeforeEnable -contains 'summon_binding' -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'plan_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'requires_explicit_operator_execution' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'mutation_authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Stage6PrerequisiteBringupPlanGovernance -Name 'would_mutate' -Default $true)
)

$Stage6BlockerFamilyHandoffs = @()
foreach ($Family in @($Stage6BlockedFamilies)) {
  $FamilyBlockers = ConvertTo-StringArray -Value (
    Get-PropertyValue -Payload $Stage6BlockerGroups -Name $Family -Default @()
  )
  $Handoff = New-BlockerFamilyHandoff -Family $Family -Blockers $FamilyBlockers
  if ($null -ne $Handoff) {
    $Stage6BlockerFamilyHandoffs += $Handoff
  }
}

$FirstBlockerFamilyHandoff = if (@($Stage6BlockerFamilyHandoffs).Count -gt 0) {
  $Stage6BlockerFamilyHandoffs[0]
} else {
  $null
}

$AllFamilyHandoffsBounded = $true
foreach ($Handoff in @($Stage6BlockerFamilyHandoffs)) {
  if (
    -not [bool](Get-PropertyValue -Payload $Handoff -Name 'read_only_contract' -Default $false) -or
    -not [bool](Get-PropertyValue -Payload $Handoff -Name 'diagnostic_only' -Default $false) -or
    [bool](Get-PropertyValue -Payload $Handoff -Name 'authority_granted' -Default $true) -or
    [bool](Get-PropertyValue -Payload $Handoff -Name 'would_execute' -Default $true) -or
    [bool](Get-PropertyValue -Payload $Handoff -Name 'would_mutate' -Default $true)
  ) {
    $AllFamilyHandoffsBounded = $false
  }
}

$FirstBlockerFamilyHandoffObserved = (
  @($Stage6BlockedFamilies).Count -gt 0 -and
  @($Stage6BlockerFamilyHandoffs).Count -eq @($Stage6BlockedFamilies).Count -and
  [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'id' -Default '') -eq [string]$Stage6BlockedFamilies[0] -and
  [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'id' -Default '') -eq 'resident_host' -and
  [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'proof_script' -Default '') -eq 'scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'route' -Default '') -eq '/lens/host' -and
  [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'readiness_route' -Default '') -eq '/lens/host/runtime-loop/readiness' -and
  [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_host_runtime_blocker_boundary' -and
  [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'authority_required' -Default '') -eq 'resident_runtime_execution_authority' -and
  $AllFamilyHandoffsBounded
)
$FirstBlockerFamilyCompletionAuditHandoffObserved = (
  [bool](Get-PropertyValue -Payload $LensStatusRead -Name 'ok' -Default $false) -and
  [string](Get-PropertyValue -Payload $Stage6ClosureReadback -Name 'kind' -Default '') -eq 'lens.stage6.closure_readback' -and
  [string](Get-PropertyValue -Payload $SummonAnywhereClosureCriterion -Name 'id' -Default '') -eq 'summon_anywhere' -and
  [string](Get-PropertyValue -Payload $SummonAnywhereClosureCriterion -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $SummonAnywhereClosureCriterion -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  [string](Get-PropertyValue -Payload $SummonAnywhereClosureHandoff -Name 'first_blocker_family' -Default '') -eq 'resident_host' -and
  [string](Get-PropertyValue -Payload $FirstBlockerFamilyCompletionAuditHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit' -and
  [string](Get-PropertyValue -Payload $FirstBlockerFamilyCompletionAuditHandoff -Name 'next_step' -Default '') -eq 'consume_resident_host_process_supervision_handoff_before_stage6_closure' -and
  [string](Get-PropertyValue -Payload $FirstBlockerFamilyCompletionAuditHandoff -Name 'proof_script' -Default '') -eq 'scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status -ConsumeProcessSupervisionHandoff' -and
  [string](Get-PropertyValue -Payload $FirstBlockerFamilyCompletionAuditHandoff -Name 'authority_required' -Default '') -eq 'process_supervision_authority' -and
  -not [bool](Get-PropertyValue -Payload $FirstBlockerFamilyCompletionAuditHandoff -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $FirstBlockerFamilyCompletionAuditHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $FirstBlockerFamilyCompletionAuditHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $FirstBlockerFamilyCompletionAuditHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $FirstBlockerFamilyCompletionAuditHandoff -Name 'would_mutate' -Default $true)
)
$RecommendedHandoffSource = if ($FirstBlockerFamilyHandoffObserved) { 'first_blocker_family_handoff' } else { '' }
$RecommendedNextSlice = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'next_step' -Default '')
$RecommendedProofScript = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'proof_script' -Default '')
$RecommendedRoute = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'route' -Default '')
$RecommendedReadinessRoute = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'readiness_route' -Default '')
$RecommendedAuthorityRequired = [string](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'authority_required' -Default '')
$RecommendedAuthorityGranted = [bool](Get-PropertyValue -Payload $FirstBlockerFamilyHandoff -Name 'authority_granted' -Default $false)
$RecommendedHandoff = if ($FirstBlockerFamilyHandoffObserved) { $FirstBlockerFamilyHandoff } else { [ordered]@{} }
$Stage6PrerequisiteBringupAuthorityRequired = 'resident_host_process_tray_hotkey_overlay_and_summon_prerequisites'
$Stage6PrerequisiteBringupAuthorityGranted = $false
if ($Stage6PrerequisiteBringupPlanStatus -eq 'ready_for_persistent_supervision_enablement_sequence') {
  $Stage6PrerequisiteBringupAuthorityRequired = 'persistent_supervision_enablement_sequence_authority'
}
if ($Stage6PrerequisiteBringupPlanStatus -eq 'persistent_supervision_enablement_applied') {
  $Stage6PrerequisiteBringupAuthorityRequired = 'none_readback_only'
  $Stage6PrerequisiteBringupAuthorityGranted = $true
}
$Stage6PrerequisiteBringupOperatorPlanHandoff = [ordered]@{}
if ($Stage6PrerequisiteBringupPlanObserved) {
  $Stage6PrerequisiteBringupOperatorPlanHandoff = [ordered]@{
    status = $Stage6PrerequisiteBringupPlanStatus
    previous_next_smallest_truthful_gap = 'summon_anywhere_blockers'
    next_smallest_truthful_gap = $Stage6PrerequisiteBringupPlanCurrentGap
    next_step = $Stage6PrerequisiteBringupPlanRecommendedNextSlice
    proof_script = $Stage6PrerequisiteBringupPlanRecommendedProofScript
    route = '/lens/host/persistent-supervision'
    readiness_route = '/lens/host/persistent-supervision/enablement'
    operator_plan_script = 'scripts/lens-stage6-prerequisite-bringup-plan.ps1'
    current_truthful_gap = $Stage6PrerequisiteBringupPlanCurrentGap
    current_truthful_gap_basis = $Stage6PrerequisiteBringupPlanCurrentGapBasis
    current_first_missing_requirement = $Stage6PrerequisiteBringupPlanFirstMissingRequirement
    current_first_missing_truthful_gap = $Stage6PrerequisiteBringupPlanFirstMissingTruthfulGap
    next_operator_action_requirement = $Stage6PrerequisiteBringupPlanNextOperatorRequirement
    next_operator_action = $Stage6PrerequisiteBringupPlanNextOperatorAction
    next_operator_command = $Stage6PrerequisiteBringupPlanNextOperatorCommand
    required_before_enable = [string[]]@($Stage6PrerequisiteBringupPlanRequiredBeforeEnable)
    missing_required_before_enable = [string[]]@($Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable)
    required_before_enable_ready = $Stage6PrerequisiteBringupPlanRequiredBeforeEnableReady
    applied = $Stage6PrerequisiteBringupPlanApplied
    authority_required = $Stage6PrerequisiteBringupAuthorityRequired
    authority_granted = $Stage6PrerequisiteBringupAuthorityGranted
    read_only_contract = $true
    diagnostic_only = $true
    plan_only = $true
    requires_explicit_operator_execution = $true
    would_execute = $false
    would_mutate = $false
    blockers = [string[]]@(@(
        $Stage6PrerequisiteBringupPlanCurrentGap,
        $Stage6PrerequisiteBringupPlanFirstMissingTruthfulGap
      ) | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Sort-Object -Unique)
  }

  if ($Stage6PrerequisiteBringupNeedsOperatorPlanHandoff) {
    $RecommendedHandoffSource = 'stage6_prerequisite_bringup_operator_plan'
    $RecommendedNextSlice = [string]$Stage6PrerequisiteBringupOperatorPlanHandoff.next_step
    $RecommendedProofScript = [string]$Stage6PrerequisiteBringupOperatorPlanHandoff.proof_script
    $RecommendedRoute = [string]$Stage6PrerequisiteBringupOperatorPlanHandoff.route
    $RecommendedReadinessRoute = [string]$Stage6PrerequisiteBringupOperatorPlanHandoff.readiness_route
    $RecommendedAuthorityRequired = [string]$Stage6PrerequisiteBringupOperatorPlanHandoff.authority_required
    $RecommendedAuthorityGranted = [bool]$Stage6PrerequisiteBringupOperatorPlanHandoff.authority_granted
    $RecommendedHandoff = $Stage6PrerequisiteBringupOperatorPlanHandoff
  }
}

$RecommendedConcreteHandoffSource = $RecommendedHandoffSource
$RecommendedConcreteHandoff = $RecommendedHandoff
if ($FirstBlockerFamilyCompletionAuditHandoffObserved) {
  $RecommendedConcreteHandoffSource = 'first_blocker_family_completion_audit_handoff'
  $RecommendedConcreteHandoff = $FirstBlockerFamilyCompletionAuditHandoff
}
$RecommendedConcreteNextSlice = [string](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'next_step' -Default $RecommendedNextSlice)
$RecommendedConcreteProofScript = [string](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'proof_script' -Default $RecommendedProofScript)
$RecommendedConcreteNextGap = [string](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'next_smallest_truthful_gap' -Default 'summon_anywhere_blockers')
$RecommendedConcreteAuthorityRequired = [string](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'authority_required' -Default $RecommendedAuthorityRequired)
$RecommendedConcreteAuthorityGranted = [bool](Get-PropertyValue -Payload $RecommendedConcreteHandoff -Name 'authority_granted' -Default $RecommendedAuthorityGranted)

$Checks = @(
  (New-Check -Id 'summon_preflight_readback' -Status $(if ($SummonPreflightObserved) { 'blocked_readback_ready' } else { 'missing_or_unexpected' }) -Passed $SummonPreflightObserved -Evidence 'scripts/lens-summon-preflight.ps1 -Mode Status' -Reason 'The direct summon preflight must name summon-anywhere as blocked and point to summon_anywhere_blockers.'),
  (New-Check -Id 'stage6_family_projection' -Status $(if ($Stage6FamilyProjectionObserved) { 'blocked_families_projected' } else { 'missing_or_unexpected' }) -Passed $Stage6FamilyProjectionObserved -Evidence 'summon preflight blockers projected into Stage 6 acceptance families' -Reason 'The handoff proof must expose the same blocker-family shape used by the Stage 6 completion audit.'),
  (New-Check -Id 'first_blocker_family_handoff' -Status $(if ($FirstBlockerFamilyHandoffObserved) { 'handoff_ready' } else { 'missing_or_unexpected' }) -Passed $FirstBlockerFamilyHandoffObserved -Evidence 'summon first blocker family to resident-host proof script' -Reason 'The aggregate summon-anywhere blocker proof must hand the first blocked acceptance family to its bounded proof without granting authority.'),
  (New-Check -Id 'summon_side_effects_denied' -Status $(if ($SideEffectsDenied) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $SideEffectsDenied -Evidence 'lens.summon.preflight.governance' -Reason 'The proof must not grant summon, hotkey, overlay, process, memory, capture, sensing, approval-decision, or execution authority.'),
  (New-Check -Id 'os_binding_authority_request_readback' -Status $(if ($OsBindingAuthorityRequestReadbackObserved) { 'readback_ready' } else { 'missing_or_unexpected' }) -Passed $OsBindingAuthorityRequestReadbackObserved -Evidence '/lens/status:/lens/os-binding/authority/requests' -Reason 'The summon-anywhere blocker proof must consume OS-binding authority request readback before treating command-palette authority visibility as audited.'),
  (New-Check -Id 'first_blocker_family_completion_audit_handoff' -Status $(if ($FirstBlockerFamilyCompletionAuditHandoffObserved) { 'closure_handoff_ready' } else { 'not_present' }) -Passed $true -Evidence '/lens/status stage6_readiness.closure_readback' -Reason 'When Lens status exposes the summon-anywhere resident-host completion-audit handoff, the aggregate proof should project it separately from the default family front door.'),
  (New-Check -Id 'stage6_prerequisite_bringup_plan' -Status $(if ($Stage6PrerequisiteBringupPlanObserved -and $Stage6PrerequisiteBringupPlanApplied) { 'applied_readback_ready' } elseif ($Stage6PrerequisiteBringupPlanObserved) { 'operator_plan_readback_ready' } elseif ($Stage6PrerequisiteBringupPlanPresent) { 'missing_or_unexpected' } else { 'not_present' }) -Passed $(-not $Stage6PrerequisiteBringupPlanPresent -or $Stage6PrerequisiteBringupPlanObserved) -Evidence '/lens/status stage6_readiness.prerequisite_bringup' -Reason 'When Lens status exposes the governed Stage 6 prerequisite bring-up plan, the aggregate summon-anywhere proof should consume its readback without routing back to an already-applied operator handoff.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.summon_anywhere_blockers.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  acceptance_criterion = 'summon_anywhere'
  next_smallest_truthful_gap = 'summon_anywhere_blockers'
  recommended_handoff_source = $RecommendedHandoffSource
  recommended_next_slice = $RecommendedNextSlice
  recommended_proof_script = $RecommendedProofScript
  recommended_route = $RecommendedRoute
  recommended_readiness_route = $RecommendedReadinessRoute
  recommended_authority_required = $RecommendedAuthorityRequired
  recommended_authority_granted = $RecommendedAuthorityGranted
  authority_required = $RecommendedAuthorityRequired
  authority_granted = $RecommendedAuthorityGranted
  recommended_handoff = $RecommendedHandoff
  recommended_concrete_handoff_source = $RecommendedConcreteHandoffSource
  recommended_concrete_next_slice = $RecommendedConcreteNextSlice
  recommended_concrete_proof_script = $RecommendedConcreteProofScript
  recommended_concrete_next_smallest_truthful_gap = $RecommendedConcreteNextGap
  recommended_concrete_authority_required = $RecommendedConcreteAuthorityRequired
  recommended_concrete_authority_granted = $RecommendedConcreteAuthorityGranted
  recommended_concrete_handoff = $RecommendedConcreteHandoff
  summon_preflight_observed = $SummonPreflightObserved
  stage6_family_projection_observed = $Stage6FamilyProjectionObserved
  side_effects_denied = $SideEffectsDenied
  os_binding_authority_request_readback_observed = $OsBindingAuthorityRequestReadbackObserved
  first_blocker_family_handoff_observed = $FirstBlockerFamilyHandoffObserved
  first_blocker_family_completion_audit_handoff_observed = $FirstBlockerFamilyCompletionAuditHandoffObserved
  first_blocker_family = if (@($Stage6BlockedFamilies).Count -gt 0) { [string]$Stage6BlockedFamilies[0] } else { '' }
  first_blocker_family_handoff = $FirstBlockerFamilyHandoff
  first_blocker_family_completion_audit_handoff = $FirstBlockerFamilyCompletionAuditHandoff
  blocked_families = [string[]]@($Stage6BlockedFamilies)
  blocked_family_handoffs = @($Stage6BlockerFamilyHandoffs)
  stage6_prerequisite_bringup_plan_observed = $Stage6PrerequisiteBringupPlanObserved
  stage6_prerequisite_bringup_plan_applied = $Stage6PrerequisiteBringupPlanApplied
  stage6_prerequisite_bringup_operator_plan_handoff = $Stage6PrerequisiteBringupOperatorPlanHandoff
  stage6_prerequisite_bringup_plan = [ordered]@{
    present = $Stage6PrerequisiteBringupPlanPresent
    kind = $Stage6PrerequisiteBringupPlanKind
    status = $Stage6PrerequisiteBringupPlanStatus
    current_truthful_gap = $Stage6PrerequisiteBringupPlanCurrentGap
    current_truthful_gap_basis = $Stage6PrerequisiteBringupPlanCurrentGapBasis
    current_first_missing_requirement = $Stage6PrerequisiteBringupPlanFirstMissingRequirement
    current_first_missing_truthful_gap = $Stage6PrerequisiteBringupPlanFirstMissingTruthfulGap
    next_operator_action_requirement = $Stage6PrerequisiteBringupPlanNextOperatorRequirement
    next_operator_action = $Stage6PrerequisiteBringupPlanNextOperatorAction
    next_operator_command = $Stage6PrerequisiteBringupPlanNextOperatorCommand
    required_before_enable = [string[]]@($Stage6PrerequisiteBringupPlanRequiredBeforeEnable)
    missing_required_before_enable = [string[]]@($Stage6PrerequisiteBringupPlanMissingRequiredBeforeEnable)
    required_before_enable_ready = $Stage6PrerequisiteBringupPlanRequiredBeforeEnableReady
    applied = $Stage6PrerequisiteBringupPlanApplied
    recommended_next_slice = $Stage6PrerequisiteBringupPlanRecommendedNextSlice
    recommended_proof_script = $Stage6PrerequisiteBringupPlanRecommendedProofScript
  }
  blocker_groups = $Stage6BlockerGroups
  blockers = [string[]]@($SummonPreflightBlockers)
  lens_status_readback = [ordered]@{
    ok = [bool](Get-PropertyValue -Payload $LensStatusRead -Name 'ok' -Default $false)
    source = [string](Get-PropertyValue -Payload $LensStatusRead -Name 'source' -Default '')
    evidence = [string](Get-PropertyValue -Payload $LensStatusRead -Name 'evidence' -Default '')
    error = [string](Get-PropertyValue -Payload $LensStatusRead -Name 'error' -Default '')
  }
  os_binding_authority_request_readback = [ordered]@{
    status = if ($OsBindingAuthorityRequestReadbackObserved) { [string](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'status' -Default '') } else { 'missing_or_failed' }
    ok = $OsBindingAuthorityRequestReadbackObserved
    evidence = [string[]]@('/lens/status', '/lens/os-binding/readiness', '/lens/os-binding/authority/requests')
    kind = [string](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'kind' -Default '')
    route = [string](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'route' -Default '')
    authority_route = [string](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'authority_route' -Default '')
    request_route = [string](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'request_route' -Default '')
    readiness_route = [string](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'readiness_route' -Default '')
    plan_route = [string](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'plan_route' -Default '')
    stage6_criterion_status = $OsBindingReadinessAuthorityRequestStatus
    stage6_criterion_readback_ready = $OsBindingReadinessAuthorityRequestReady
    authority_required = [string](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'authority_required' -Default '')
    pending_count = [int](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'pending_count' -Default 0)
    approved_count = [int](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'approved_count' -Default 0)
    rejected_count = [int](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'rejected_count' -Default 0)
    emergency_count = [int](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'emergency_count' -Default 0)
    total_count = [int](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'total_count' -Default 0)
    authority_granted = [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'authority_granted' -Default $false)
    os_level_command_palette_binding_authority = [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'os_level_command_palette_binding_authority' -Default $false)
    os_level_command_palette = [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'os_level_command_palette' -Default $false)
    summon_anywhere = [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'summon_anywhere' -Default $false)
    opens_palette = [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'opens_palette' -Default $false)
    registers_hotkey = [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'registers_hotkey' -Default $false)
    launches_process = [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'launches_process' -Default $false)
    controls_overlay = [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequests -Name 'controls_overlay' -Default $false)
    governance = [ordered]@{
      read_only_contract = [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequestsGovernance -Name 'read_only_contract' -Default $false)
      approval_request_write = [bool](Get-PropertyValue -Payload $OsBindingAuthorityRequestsGovernance -Name 'approval_request_write' -Default $true)
      execution_authority = $false
      approval_decision_authority = $false
      memory_write = $false
      resident_claim_authority = $false
    }
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
  }
  checks = @($Checks)
  evidence = @(
    'scripts/lens-summon-preflight.ps1 -Mode Status',
    '/lens/status stage6_readiness.prerequisite_bringup',
    'config/runtime/lens/summon.json',
    'docs/operations/COMPLETION_LEDGER.md',
    'docs/canonical/ROADMAP.md#4.12'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_summon_preflight = $true
    wraps_lens_status = $true
    read_only_contract = [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'read_only_contract' -Default $false)
    os_binding_authority_request_readback = $OsBindingAuthorityRequestReadbackObserved
    first_blocker_family_handoff_readback = $FirstBlockerFamilyHandoffObserved
    first_blocker_family_completion_audit_handoff_readback = $FirstBlockerFamilyCompletionAuditHandoffObserved
    stage6_prerequisite_bringup_plan_readback = $Stage6PrerequisiteBringupPlanObserved
    approval_request_write = $false
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    local_process_launch_authority = $false
    hotkey_registration_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = $(if ($Stage6PrerequisiteBringupPlanObserved) { 'Stage 6 summon-anywhere remains blocked; this proof preserves the blocker-family inventory while handing the next concrete step to the governed Stage 6 prerequisite bring-up plan readback.' } else { 'Stage 6 summon-anywhere remains blocked by resident host, tray, overlay, global hotkey binding, summon binding, and authority gaps; this proof is read-only and grants no summon or runtime authority.' })
}

$Payload | ConvertTo-Json -Depth 8
exit $(if ($ProofPassed) { 0 } else { 1 })
