[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$ManifestPath = '',

  [string]$MeasurementPath = '',

  [string]$MockupPath = '',

  [string]$MannequinPath = '',

  [string]$StaticFitPath = '',

  [string]$MovementPath = '',

  [string]$ReleaseCablePath = '',

  [string]$EngineeringReviewPath = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Add-OptionalArg {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [string]$Name,
    [string]$Value
  )

  if (-not [string]::IsNullOrWhiteSpace($Value)) {
    $Target.Add($Name) | Out-Null
    $Target.Add($Value) | Out-Null
  }
}

function Invoke-JsonGate {
  param(
    [string]$ScriptName,
    [string[]]$Arguments
  )

  $PowerShellExe = (Get-Process -Id $PID).Path
  $ScriptPath = Join-Path $PSScriptRoot $ScriptName
  $GateArgs = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $ScriptPath
  ) + $Arguments

  $RawOutput = & $PowerShellExe @GateArgs
  $GateExitCode = $LASTEXITCODE
  $Payload = $null
  $ParseOk = $false
  try {
    $Payload = ($RawOutput | Out-String) | ConvertFrom-Json -ErrorAction Stop
    $ParseOk = $true
  } catch {
    $Payload = $null
  }

  return [ordered]@{
    exit_code = $GateExitCode
    parse_ok = $ParseOk
    payload = $Payload
  }
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

function Get-PayloadArrayProperty {
  param(
    [object]$Payload,
    [string]$Name
  )

  if ($null -eq $Payload) {
    return @()
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property) {
    return @()
  }
  return @(ConvertTo-StringArray -Value $Property.Value)
}

function Get-PayloadObjectArrayProperty {
  param(
    [object]$Payload,
    [string]$Name
  )

  if ($null -eq $Payload) {
    return @()
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return @()
  }
  if ($Property.Value -is [System.Array]) {
    return @($Property.Value)
  }
  return @($Property.Value)
}

function New-GateEvidenceDetails {
  param([object]$Payload)

  return [ordered]@{
    missing_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'missing_fields')
    invalid_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'invalid_fields')
    measurement_consistency_violations = @(Get-PayloadArrayProperty -Payload $Payload -Name 'measurement_consistency_violations')
    marked_zone_specificity_violations = @(Get-PayloadArrayProperty -Payload $Payload -Name 'marked_zone_specificity_violations')
    upstream_marked_zone_specificity_violations = @(Get-PayloadArrayProperty -Payload $Payload -Name 'upstream_marked_zone_specificity_violations')
    repeatability_blockers = @(Get-PayloadArrayProperty -Payload $Payload -Name 'repeatability_blockers')
    left_right_independence_blockers = @(Get-PayloadArrayProperty -Payload $Payload -Name 'left_right_independence_blockers')
    upstream_left_right_independence_blockers = @(Get-PayloadArrayProperty -Payload $Payload -Name 'upstream_left_right_independence_blockers')
    measurement_condition_blockers = @(Get-PayloadArrayProperty -Payload $Payload -Name 'measurement_condition_blockers')
    upstream_measurement_condition_blockers = @(Get-PayloadArrayProperty -Payload $Payload -Name 'upstream_measurement_condition_blockers')
    landmark_confirmation_blockers = @(Get-PayloadArrayProperty -Payload $Payload -Name 'landmark_confirmation_blockers')
    upstream_landmark_confirmation_blockers = @(Get-PayloadArrayProperty -Payload $Payload -Name 'upstream_landmark_confirmation_blockers')
    measurement_note_blockers = @(Get-PayloadArrayProperty -Payload $Payload -Name 'measurement_note_blockers')
    upstream_measurement_note_blockers = @(Get-PayloadArrayProperty -Payload $Payload -Name 'upstream_measurement_note_blockers')
    safety_blockers = @(Get-PayloadArrayProperty -Payload $Payload -Name 'safety_blockers')
    record_linkage_violations = @(Get-PayloadArrayProperty -Payload $Payload -Name 'record_linkage_violations')
    measurement_missing_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'measurement_missing_fields')
    measurement_invalid_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'measurement_invalid_fields')
    mockup_missing_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'mockup_missing_fields')
    mockup_invalid_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'mockup_invalid_fields')
    mockup_linkage_violations = @(Get-PayloadArrayProperty -Payload $Payload -Name 'mockup_linkage_violations')
    mockup_redesign_triggers = @(Get-PayloadArrayProperty -Payload $Payload -Name 'mockup_redesign_triggers')
    interface_redesign_triggers = @(Get-PayloadArrayProperty -Payload $Payload -Name 'interface_redesign_triggers')
    fit_redesign_triggers = @(Get-PayloadArrayProperty -Payload $Payload -Name 'fit_redesign_triggers')
    movement_redesign_triggers = @(Get-PayloadArrayProperty -Payload $Payload -Name 'movement_redesign_triggers')
    release_cable_redesign_triggers = @(Get-PayloadArrayProperty -Payload $Payload -Name 'release_cable_redesign_triggers')
    fail_observations = @(Get-PayloadArrayProperty -Payload $Payload -Name 'fail_observations')
    review_redesign_triggers = @(Get-PayloadArrayProperty -Payload $Payload -Name 'review_redesign_triggers')
    prohibited_clearance_flags = @(Get-PayloadArrayProperty -Payload $Payload -Name 'prohibited_clearance_flags')
    symptom_blockers = @(Get-PayloadArrayProperty -Payload $Payload -Name 'symptom_blockers')
    failed_checks = @(Get-PayloadArrayProperty -Payload $Payload -Name 'failed_checks')
    missing_measurement_template_contracts = @(Get-PayloadArrayProperty -Payload $Payload -Name 'missing_measurement_template_contracts')
    missing_measurement_template_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'missing_measurement_template_fields')
    missing_mockup_template_contracts = @(Get-PayloadArrayProperty -Payload $Payload -Name 'missing_mockup_template_contracts')
    missing_mockup_template_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'missing_mockup_template_fields')
    missing_mannequin_template_contracts = @(Get-PayloadArrayProperty -Payload $Payload -Name 'missing_mannequin_template_contracts')
    missing_mannequin_template_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'missing_mannequin_template_fields')
    missing_static_fit_template_contracts = @(Get-PayloadArrayProperty -Payload $Payload -Name 'missing_static_fit_template_contracts')
    missing_static_fit_template_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'missing_static_fit_template_fields')
    missing_movement_template_contracts = @(Get-PayloadArrayProperty -Payload $Payload -Name 'missing_movement_template_contracts')
    missing_movement_template_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'missing_movement_template_fields')
    missing_release_cable_template_contracts = @(Get-PayloadArrayProperty -Payload $Payload -Name 'missing_release_cable_template_contracts')
    missing_release_cable_template_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'missing_release_cable_template_fields')
    missing_engineering_template_contracts = @(Get-PayloadArrayProperty -Payload $Payload -Name 'missing_engineering_template_contracts')
    missing_engineering_template_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'missing_engineering_template_fields')
    failed_reasons = @(Get-PayloadArrayProperty -Payload $Payload -Name 'failed_reasons')
    evidence_chronology_violations = @(Get-PayloadArrayProperty -Payload $Payload -Name 'evidence_chronology_violations')
    pilot_identity_continuity_violations = @(Get-PayloadArrayProperty -Payload $Payload -Name 'pilot_identity_continuity_violations')
    pilot_identity_continuity_reference_record = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['pilot_identity_continuity_reference_record']) { '' } else { [string]$Payload.pilot_identity_continuity_reference_record }
    pilot_identity_continuity_reference_fingerprint = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['pilot_identity_continuity_reference_fingerprint']) { '' } else { [string]$Payload.pilot_identity_continuity_reference_fingerprint }
    next_required_physical_input = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['next_required_physical_input']) { '' } else { [string]$Payload.next_required_physical_input }
    measurement_capture_plan_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_plan_contract']) { '' } else { [string]$Payload.measurement_capture_plan_contract }
    measurement_capture_plan_status_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_plan_status_contract']) { '' } else { [string]$Payload.measurement_capture_plan_status_contract }
    measurement_capture_summary_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_summary_contract']) { '' } else { [string]$Payload.measurement_capture_summary_contract }
    measurement_capture_plan_not_completion_evidence = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_plan_not_completion_evidence']) { $false } else { [bool]$Payload.measurement_capture_plan_not_completion_evidence }
    measurement_capture_plan = @(Get-PayloadObjectArrayProperty -Payload $Payload -Name 'measurement_capture_plan')
    measurement_capture_plan_status = @(Get-PayloadObjectArrayProperty -Payload $Payload -Name 'measurement_capture_plan_status')
    measurement_capture_total_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_total_groups']) { 0 } else { [int]$Payload.measurement_capture_total_groups }
    measurement_capture_ready_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_ready_groups']) { 0 } else { [int]$Payload.measurement_capture_ready_groups }
    measurement_capture_pending_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_pending_groups']) { 0 } else { [int]$Payload.measurement_capture_pending_groups }
    measurement_capture_invalid_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_invalid_groups']) { 0 } else { [int]$Payload.measurement_capture_invalid_groups }
    measurement_capture_failed_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_failed_groups']) { 0 } else { [int]$Payload.measurement_capture_failed_groups }
    measurement_capture_first_blocking_group_id = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_first_blocking_group_id']) { '' } else { [string]$Payload.measurement_capture_first_blocking_group_id }
    measurement_capture_first_blocking_group_status = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_first_blocking_group_status']) { '' } else { [string]$Payload.measurement_capture_first_blocking_group_status }
    measurement_capture_first_blocking_group_action = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_first_blocking_group_action']) { '' } else { [string]$Payload.measurement_capture_first_blocking_group_action }
    mockup_capture_plan_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_plan_contract']) { '' } else { [string]$Payload.mockup_capture_plan_contract }
    mockup_capture_plan_status_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_plan_status_contract']) { '' } else { [string]$Payload.mockup_capture_plan_status_contract }
    mockup_capture_summary_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_summary_contract']) { '' } else { [string]$Payload.mockup_capture_summary_contract }
    mockup_capture_plan_not_completion_evidence = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_plan_not_completion_evidence']) { $false } else { [bool]$Payload.mockup_capture_plan_not_completion_evidence }
    next_required_mockup_input = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['next_required_mockup_input']) { '' } else { [string]$Payload.next_required_mockup_input }
    mockup_capture_plan = @(Get-PayloadObjectArrayProperty -Payload $Payload -Name 'mockup_capture_plan')
    mockup_capture_plan_status = @(Get-PayloadObjectArrayProperty -Payload $Payload -Name 'mockup_capture_plan_status')
    mockup_capture_total_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_total_groups']) { 0 } else { [int]$Payload.mockup_capture_total_groups }
    mockup_capture_ready_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_ready_groups']) { 0 } else { [int]$Payload.mockup_capture_ready_groups }
    mockup_capture_pending_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_pending_groups']) { 0 } else { [int]$Payload.mockup_capture_pending_groups }
    mockup_capture_invalid_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_invalid_groups']) { 0 } else { [int]$Payload.mockup_capture_invalid_groups }
    mockup_capture_failed_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_failed_groups']) { 0 } else { [int]$Payload.mockup_capture_failed_groups }
    mockup_capture_upstream_blocked_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_upstream_blocked_groups']) { 0 } else { [int]$Payload.mockup_capture_upstream_blocked_groups }
    mockup_capture_first_blocking_group_id = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_first_blocking_group_id']) { '' } else { [string]$Payload.mockup_capture_first_blocking_group_id }
    mockup_capture_first_blocking_group_status = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_first_blocking_group_status']) { '' } else { [string]$Payload.mockup_capture_first_blocking_group_status }
    mockup_capture_first_blocking_group_action = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_first_blocking_group_action']) { '' } else { [string]$Payload.mockup_capture_first_blocking_group_action }
    mannequin_capture_plan_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_plan_contract']) { '' } else { [string]$Payload.mannequin_capture_plan_contract }
    mannequin_capture_plan_status_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_plan_status_contract']) { '' } else { [string]$Payload.mannequin_capture_plan_status_contract }
    mannequin_capture_summary_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_summary_contract']) { '' } else { [string]$Payload.mannequin_capture_summary_contract }
    mannequin_capture_plan_not_completion_evidence = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_plan_not_completion_evidence']) { $false } else { [bool]$Payload.mannequin_capture_plan_not_completion_evidence }
    next_required_mannequin_input = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['next_required_mannequin_input']) { '' } else { [string]$Payload.next_required_mannequin_input }
    mannequin_capture_plan = @(Get-PayloadObjectArrayProperty -Payload $Payload -Name 'mannequin_capture_plan')
    mannequin_capture_plan_status = @(Get-PayloadObjectArrayProperty -Payload $Payload -Name 'mannequin_capture_plan_status')
    mannequin_capture_total_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_total_groups']) { 0 } else { [int]$Payload.mannequin_capture_total_groups }
    mannequin_capture_ready_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_ready_groups']) { 0 } else { [int]$Payload.mannequin_capture_ready_groups }
    mannequin_capture_pending_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_pending_groups']) { 0 } else { [int]$Payload.mannequin_capture_pending_groups }
    mannequin_capture_invalid_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_invalid_groups']) { 0 } else { [int]$Payload.mannequin_capture_invalid_groups }
    mannequin_capture_failed_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_failed_groups']) { 0 } else { [int]$Payload.mannequin_capture_failed_groups }
    mannequin_capture_upstream_blocked_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_upstream_blocked_groups']) { 0 } else { [int]$Payload.mannequin_capture_upstream_blocked_groups }
    mannequin_capture_first_blocking_group_id = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_first_blocking_group_id']) { '' } else { [string]$Payload.mannequin_capture_first_blocking_group_id }
    mannequin_capture_first_blocking_group_status = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_first_blocking_group_status']) { '' } else { [string]$Payload.mannequin_capture_first_blocking_group_status }
    mannequin_capture_first_blocking_group_action = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_first_blocking_group_action']) { '' } else { [string]$Payload.mannequin_capture_first_blocking_group_action }
    static_fit_capture_plan_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_plan_contract']) { '' } else { [string]$Payload.static_fit_capture_plan_contract }
    static_fit_capture_plan_status_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_plan_status_contract']) { '' } else { [string]$Payload.static_fit_capture_plan_status_contract }
    static_fit_capture_summary_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_summary_contract']) { '' } else { [string]$Payload.static_fit_capture_summary_contract }
    static_fit_capture_plan_not_completion_evidence = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_plan_not_completion_evidence']) { $false } else { [bool]$Payload.static_fit_capture_plan_not_completion_evidence }
    next_required_static_fit_input = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['next_required_static_fit_input']) { '' } else { [string]$Payload.next_required_static_fit_input }
    static_fit_capture_plan = @(Get-PayloadObjectArrayProperty -Payload $Payload -Name 'static_fit_capture_plan')
    static_fit_capture_plan_status = @(Get-PayloadObjectArrayProperty -Payload $Payload -Name 'static_fit_capture_plan_status')
    static_fit_capture_total_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_total_groups']) { 0 } else { [int]$Payload.static_fit_capture_total_groups }
    static_fit_capture_ready_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_ready_groups']) { 0 } else { [int]$Payload.static_fit_capture_ready_groups }
    static_fit_capture_pending_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_pending_groups']) { 0 } else { [int]$Payload.static_fit_capture_pending_groups }
    static_fit_capture_invalid_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_invalid_groups']) { 0 } else { [int]$Payload.static_fit_capture_invalid_groups }
    static_fit_capture_failed_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_failed_groups']) { 0 } else { [int]$Payload.static_fit_capture_failed_groups }
    static_fit_capture_upstream_blocked_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_upstream_blocked_groups']) { 0 } else { [int]$Payload.static_fit_capture_upstream_blocked_groups }
    static_fit_capture_first_blocking_group_id = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_first_blocking_group_id']) { '' } else { [string]$Payload.static_fit_capture_first_blocking_group_id }
    static_fit_capture_first_blocking_group_status = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_first_blocking_group_status']) { '' } else { [string]$Payload.static_fit_capture_first_blocking_group_status }
    static_fit_capture_first_blocking_group_action = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_first_blocking_group_action']) { '' } else { [string]$Payload.static_fit_capture_first_blocking_group_action }
    next_actions = @(Get-PayloadArrayProperty -Payload $Payload -Name 'next_actions')
  }
}

function New-GateDefinition {
  param(
    [string]$Id,
    [string]$ScriptName,
    [string]$ReadyStatus,
    [string]$NextRequiredInput,
    [string]$NextCommand,
    [string[]]$Arguments
  )

  return [ordered]@{
    id = $Id
    script_name = $ScriptName
    ready_status = $ReadyStatus
    next_required_input = $NextRequiredInput
    next_command = $NextCommand
    arguments = $Arguments
  }
}

$PackageArgs = New-Object System.Collections.Generic.List[string]
$PackageArgs.Add('-Mode') | Out-Null
$PackageArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $PackageArgs -Name '-ManifestPath' -Value $ManifestPath

$MeasurementArgs = New-Object System.Collections.Generic.List[string]
$MeasurementArgs.Add('-Mode') | Out-Null
$MeasurementArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $MeasurementArgs -Name '-MeasurementPath' -Value $MeasurementPath

$MockupArgs = New-Object System.Collections.Generic.List[string]
$MockupArgs.Add('-Mode') | Out-Null
$MockupArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $MockupArgs -Name '-MeasurementPath' -Value $MeasurementPath
Add-OptionalArg -Target $MockupArgs -Name '-MockupPath' -Value $MockupPath

$MannequinArgs = New-Object System.Collections.Generic.List[string]
$MannequinArgs.Add('-Mode') | Out-Null
$MannequinArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $MannequinArgs -Name '-MeasurementPath' -Value $MeasurementPath
Add-OptionalArg -Target $MannequinArgs -Name '-MockupPath' -Value $MockupPath
Add-OptionalArg -Target $MannequinArgs -Name '-MannequinPath' -Value $MannequinPath

$StaticFitArgs = New-Object System.Collections.Generic.List[string]
$StaticFitArgs.Add('-Mode') | Out-Null
$StaticFitArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $StaticFitArgs -Name '-MeasurementPath' -Value $MeasurementPath
Add-OptionalArg -Target $StaticFitArgs -Name '-MockupPath' -Value $MockupPath
Add-OptionalArg -Target $StaticFitArgs -Name '-MannequinPath' -Value $MannequinPath
Add-OptionalArg -Target $StaticFitArgs -Name '-StaticFitPath' -Value $StaticFitPath

$MovementArgs = New-Object System.Collections.Generic.List[string]
$MovementArgs.Add('-Mode') | Out-Null
$MovementArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $MovementArgs -Name '-MeasurementPath' -Value $MeasurementPath
Add-OptionalArg -Target $MovementArgs -Name '-MockupPath' -Value $MockupPath
Add-OptionalArg -Target $MovementArgs -Name '-MannequinPath' -Value $MannequinPath
Add-OptionalArg -Target $MovementArgs -Name '-StaticFitPath' -Value $StaticFitPath
Add-OptionalArg -Target $MovementArgs -Name '-MovementPath' -Value $MovementPath

$ReleaseCableArgs = New-Object System.Collections.Generic.List[string]
$ReleaseCableArgs.Add('-Mode') | Out-Null
$ReleaseCableArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $ReleaseCableArgs -Name '-MeasurementPath' -Value $MeasurementPath
Add-OptionalArg -Target $ReleaseCableArgs -Name '-MockupPath' -Value $MockupPath
Add-OptionalArg -Target $ReleaseCableArgs -Name '-MannequinPath' -Value $MannequinPath
Add-OptionalArg -Target $ReleaseCableArgs -Name '-StaticFitPath' -Value $StaticFitPath
Add-OptionalArg -Target $ReleaseCableArgs -Name '-MovementPath' -Value $MovementPath
Add-OptionalArg -Target $ReleaseCableArgs -Name '-ReleaseCablePath' -Value $ReleaseCablePath

$EngineeringArgs = New-Object System.Collections.Generic.List[string]
$EngineeringArgs.Add('-Mode') | Out-Null
$EngineeringArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $EngineeringArgs -Name '-MeasurementPath' -Value $MeasurementPath
Add-OptionalArg -Target $EngineeringArgs -Name '-MockupPath' -Value $MockupPath
Add-OptionalArg -Target $EngineeringArgs -Name '-MannequinPath' -Value $MannequinPath
Add-OptionalArg -Target $EngineeringArgs -Name '-StaticFitPath' -Value $StaticFitPath
Add-OptionalArg -Target $EngineeringArgs -Name '-MovementPath' -Value $MovementPath
Add-OptionalArg -Target $EngineeringArgs -Name '-ReleaseCablePath' -Value $ReleaseCablePath
Add-OptionalArg -Target $EngineeringArgs -Name '-EngineeringReviewPath' -Value $EngineeringReviewPath

$FinalArgs = New-Object System.Collections.Generic.List[string]
$FinalArgs.Add('-Mode') | Out-Null
$FinalArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $FinalArgs -Name '-ManifestPath' -Value $ManifestPath
Add-OptionalArg -Target $FinalArgs -Name '-MeasurementPath' -Value $MeasurementPath
Add-OptionalArg -Target $FinalArgs -Name '-MockupPath' -Value $MockupPath
Add-OptionalArg -Target $FinalArgs -Name '-MannequinPath' -Value $MannequinPath
Add-OptionalArg -Target $FinalArgs -Name '-StaticFitPath' -Value $StaticFitPath
Add-OptionalArg -Target $FinalArgs -Name '-MovementPath' -Value $MovementPath
Add-OptionalArg -Target $FinalArgs -Name '-ReleaseCablePath' -Value $ReleaseCablePath
Add-OptionalArg -Target $FinalArgs -Name '-EngineeringReviewPath' -Value $EngineeringReviewPath

$Gates = @(
  (New-GateDefinition -Id 'stage17_package' -ScriptName 'fr017-stage17-validation-gate.ps1' -ReadyStatus 'blocked_physical_validation' -NextRequiredInput 'FR-017-STAGE17-PACKAGE-MANIFEST.json' -NextCommand 'correct_FR-017_package_manifest_or_records' -Arguments $PackageArgs.ToArray()),
  (New-GateDefinition -Id 'measurement_intake' -ScriptName 'fr017-measurement-intake.ps1' -ReadyStatus 'ready_for_non_powered_mockup_patterning' -NextRequiredInput 'FR-017-MEASUREMENTS-INPUT-TEMPLATE.json' -NextCommand 'complete_left_right_measurement_record_then_rerun_measurement_intake' -Arguments $MeasurementArgs.ToArray()),
  (New-GateDefinition -Id 'mockup_readiness' -ScriptName 'fr017-mockup-readiness-gate.ps1' -ReadyStatus 'ready_for_mannequin_interface_test' -NextRequiredInput 'FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json' -NextCommand 'complete_non_powered_mockup_build_record_then_rerun_mockup_readiness_gate' -Arguments $MockupArgs.ToArray()),
  (New-GateDefinition -Id 'mannequin_interface' -ScriptName 'fr017-mannequin-interface-gate.ps1' -ReadyStatus 'ready_for_pilot_static_fit_planning' -NextRequiredInput 'FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json' -NextCommand 'complete_mannequin_interface_record_then_rerun_mannequin_interface_gate' -Arguments $MannequinArgs.ToArray()),
  (New-GateDefinition -Id 'pilot_static_fit' -ScriptName 'fr017-pilot-static-fit-gate.ps1' -ReadyStatus 'ready_for_pilot_movement_test_planning' -NextRequiredInput 'FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json' -NextCommand 'complete_pilot_static_fit_record_then_rerun_pilot_static_fit_gate' -Arguments $StaticFitArgs.ToArray()),
  (New-GateDefinition -Id 'pilot_movement' -ScriptName 'fr017-pilot-movement-gate.ps1' -ReadyStatus 'ready_for_quick_release_and_cable_snag_test_planning' -NextRequiredInput 'FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json' -NextCommand 'complete_pilot_movement_record_then_rerun_pilot_movement_gate' -Arguments $MovementArgs.ToArray()),
  (New-GateDefinition -Id 'quick_release_cable_snag' -ScriptName 'fr017-quick-release-cable-snag-gate.ps1' -ReadyStatus 'ready_for_engineering_review_or_final_physical_gate_audit' -NextRequiredInput 'FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json' -NextCommand 'complete_quick_release_cable_snag_record_then_rerun_release_cable_gate' -Arguments $ReleaseCableArgs.ToArray()),
  (New-GateDefinition -Id 'engineering_review' -ScriptName 'fr017-engineering-review-gate.ps1' -ReadyStatus 'ready_for_final_stage17_physical_gate_audit' -NextRequiredInput 'FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json' -NextCommand 'complete_professional_engineering_review_record_then_rerun_engineering_review_gate' -Arguments $EngineeringArgs.ToArray()),
  (New-GateDefinition -Id 'final_physical_gate' -ScriptName 'fr017-final-physical-gate.ps1' -ReadyStatus 'ready_for_stage17_final_physical_completion_decision' -NextRequiredInput 'human_final_completion_decision' -NextCommand 'perform_human_final_stage17_completion_decision_against_real_records' -Arguments $FinalArgs.ToArray())
)

$GateResults = New-Object System.Collections.Generic.List[object]
$FirstBlockingGate = $null
$FirstBlockingStatus = ''
$NextRequiredInput = ''
$NextCommand = ''
$FirstBlockingDetails = New-GateEvidenceDetails -Payload $null
$Status = 'ready_for_stage17_final_physical_completion_decision'
$ExitCode = 0

foreach ($Gate in $Gates) {
  $Result = Invoke-JsonGate -ScriptName ([string]$Gate.script_name) -Arguments ([string[]]$Gate.arguments)
  $GateStatus = if ([bool]$Result.parse_ok) { [string]$Result.payload.status } else { 'failed_gate_parse' }
  $GateReady = [bool]$Result.parse_ok -and [int]$Result.exit_code -eq 0 -and $GateStatus -eq [string]$Gate.ready_status
  $GateFailed = (-not [bool]$Result.parse_ok) -or [int]$Result.exit_code -ne 0 -or $GateStatus.StartsWith('failed_') -or $GateStatus.StartsWith('missing_') -or $GateStatus.StartsWith('invalid_')
  $GateDetails = New-GateEvidenceDetails -Payload $Result.payload

  $GateResults.Add([ordered]@{
      id = [string]$Gate.id
      script_name = [string]$Gate.script_name
      status = $GateStatus
      ready_status = [string]$Gate.ready_status
      ready_for_next_gate = $GateReady
      failed = $GateFailed
      exit_code = [int]$Result.exit_code
      parse_ok = [bool]$Result.parse_ok
      next_required_input = [string]$Gate.next_required_input
      next_command = [string]$Gate.next_command
      details = $GateDetails
    }) | Out-Null

  if (-not $GateReady) {
    $FirstBlockingGate = [string]$Gate.id
    $FirstBlockingStatus = $GateStatus
    $NextRequiredInput = [string]$Gate.next_required_input
    $NextCommand = [string]$Gate.next_command
    $FirstBlockingDetails = $GateDetails
    if ($GateFailed) {
      $Status = 'failed_{0}' -f [string]$Gate.id
      $ExitCode = 1
    } else {
      $Status = 'blocked_on_{0}' -f [string]$Gate.id
    }
    break
  }
}

$EvidenceChainDecisionReady = $Status -eq 'ready_for_stage17_final_physical_completion_decision'

$Output = [ordered]@{
  kind = 'francis.fr017.evidence_chain_status'
  mode = $Mode
  status = $Status
  evidence_chain_decision_ready = $EvidenceChainDecisionReady
  physical_validation_complete = $false
  stage17_completion_claim_allowed = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  read_only_contract = $true
  writes_repo = $false
  writes_data = $false
  grants_execution_authority = $false
  grants_mutation_authority = $false
  first_blocking_gate = if ($null -eq $FirstBlockingGate) { '' } else { $FirstBlockingGate }
  first_blocking_status = $FirstBlockingStatus
  next_required_input = $NextRequiredInput
  next_command = $NextCommand
  first_blocking_details = $FirstBlockingDetails
  gates_ran = $GateResults.Count
  gate_count = $Gates.Count
  gate_results = @($GateResults.ToArray())
  no_fake_validation_lock = 'This chain-status command reports evidence readiness only. It never marks physical_validation_complete or clears FR-018.'
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
