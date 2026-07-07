[CmdletBinding()]
param(
  [ValidateSet('Status', 'Summary')]
  [string]$Mode = 'Status',

  [string]$ManifestPath = '',

  [string]$MeasurementPath = '',

  [string]$CandidateMeasurementPath = '',

  [string]$MockupPath = '',

  [string]$MannequinPath = '',

  [string]$StaticFitPath = '',

  [string]$MovementPath = '',

  [string]$ReleaseCablePath = '',

  [string]$EngineeringReviewPath = '',

  [string]$FinalDecisionPath = '',

  [string]$LedgerEntryPath = '',

  [string]$CompletionLedgerPath = ''
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

function Get-PayloadValue {
  param(
    [object]$Payload,
    [string]$Name,
    [object]$Default = ''
  )

  if ($null -eq $Payload) {
    return $Default
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return $Default
  }
  return $Property.Value
}

function Get-DetailsValue {
  param(
    [object]$Details,
    [string]$Name,
    [object]$Default = ''
  )

  if ($null -eq $Details) {
    return $Default
  }
  if ($Details -is [System.Collections.IDictionary]) {
    if ($Details.Contains($Name) -and $null -ne $Details[$Name]) {
      return $Details[$Name]
    }
    return $Default
  }
  return Get-PayloadValue -Payload $Details -Name $Name -Default $Default
}

function Get-DetailsArrayValue {
  param(
    [object]$Details,
    [string]$Name
  )

  $Value = Get-DetailsValue -Details $Details -Name $Name -Default @()
  return @(ConvertTo-StringArray -Value $Value)
}

function New-GateEvidenceDetails {
  param(
    [object]$Payload,
    [object]$MeasurementSessionPayload = $null,
    [bool]$MeasurementSessionParseOk = $false,
    [int]$MeasurementSessionExitCode = 0
  )

  $MeasurementSessionBriefPath = if ($null -eq $MeasurementSessionPayload) { '' } else { Join-Path $RepoRoot 'scripts\fr017-measurement-session-brief.ps1' }

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
    measurement_input_template_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_input_template_path']) { '' } else { [string]$Payload.measurement_input_template_path }
    measurement_capture_runbook_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_runbook_path']) { '' } else { [string]$Payload.measurement_capture_runbook_path }
    measurement_record_initializer_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_record_initializer_path']) { '' } else { [string]$Payload.measurement_record_initializer_path }
    measurement_setup_update_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_setup_update_path']) { '' } else { [string]$Payload.measurement_setup_update_path }
    measurement_record_update_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_record_update_path']) { '' } else { [string]$Payload.measurement_record_update_path }
    measurement_landmark_update_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_landmark_update_path']) { '' } else { [string]$Payload.measurement_landmark_update_path }
    measurement_independence_safety_update_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_independence_safety_update_path']) { '' } else { [string]$Payload.measurement_independence_safety_update_path }
    measurement_working_record_name_pattern = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_working_record_name_pattern']) { '' } else { [string]$Payload.measurement_working_record_name_pattern }
    measurement_session_brief_path = $MeasurementSessionBriefPath
    measurement_session_brief_status = [string](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'status' -Default '')
    measurement_session_brief_exit_code = $MeasurementSessionExitCode
    measurement_session_brief_parse_ok = $MeasurementSessionParseOk
    measurement_session_brief_contract = [string](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'measurement_session_brief_contract' -Default '')
    measurement_session_next_operator_action = [string](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'next_operator_action' -Default '')
    measurement_session_current_group_id = [string](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'first_blocking_group_id' -Default '')
    measurement_session_current_group_required_action = [string](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_required_action' -Default '')
    measurement_session_current_group_preflight_tool_path = [string](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_preflight_tool_path' -Default '')
    measurement_session_current_group_preflight_command_template = [string](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_preflight_command_template' -Default '')
    measurement_session_current_group_preflight_contract = [string](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_preflight_contract' -Default '')
    measurement_session_current_group_preflight_status = [string](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_preflight_status' -Default '')
    measurement_session_current_group_preflight_exit_code = [int](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_preflight_exit_code' -Default 0)
    measurement_session_current_group_preflight_parse_ok = [bool](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_preflight_parse_ok' -Default $false)
    measurement_session_current_group_preflight_read_only_contract = [bool](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_preflight_read_only_contract' -Default $false)
    measurement_session_current_group_preflight_template_exists = [bool](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_preflight_template_exists' -Default $false)
    measurement_session_current_group_preflight_template_parse_ok = [bool](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_preflight_template_parse_ok' -Default $false)
    measurement_session_current_group_preflight_candidate_output_path_ready = [bool](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_preflight_candidate_output_path_ready' -Default $false)
    measurement_session_current_group_preflight_output_path = [string](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_preflight_output_path' -Default '')
    measurement_session_current_group_preflight_output_exists = [bool](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_preflight_output_exists' -Default $false)
    measurement_session_current_group_preflight_output_parent_exists = [bool](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_preflight_output_parent_exists' -Default $false)
    measurement_session_current_group_preflight_wrote_file = [bool](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_preflight_wrote_file' -Default $false)
    measurement_session_current_group_preflight_physical_validation_complete = [bool](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_preflight_physical_validation_complete' -Default $false)
    measurement_session_current_group_preflight_stage17_completion_claim_allowed = [bool](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_preflight_stage17_completion_claim_allowed' -Default $false)
    measurement_session_current_group_preflight_fr018_implementation_cleared = [bool](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_preflight_fr018_implementation_cleared' -Default $false)
    measurement_session_current_group_missing_fields = @(Get-PayloadArrayProperty -Payload $MeasurementSessionPayload -Name 'current_group_missing_fields')
    measurement_session_current_group_invalid_fields = @(Get-PayloadArrayProperty -Payload $MeasurementSessionPayload -Name 'current_group_invalid_fields')
    measurement_session_current_group_blocking_signals = @(Get-PayloadArrayProperty -Payload $MeasurementSessionPayload -Name 'current_group_blocking_signals')
    measurement_session_current_group_update_required_input_fields = @(Get-PayloadArrayProperty -Payload $MeasurementSessionPayload -Name 'current_group_update_required_input_fields')
    measurement_session_current_group_update_tool_path = [string](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_update_tool_path' -Default '')
    measurement_session_current_group_update_command_template = [string](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_update_command_template' -Default '')
    measurement_session_current_group_update_contract = [string](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'current_group_update_contract' -Default '')
    measurement_session_measurement_capture_next_command_kind = [string](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'measurement_capture_next_command_kind' -Default '')
    measurement_session_measurement_capture_next_command_template = [string](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'measurement_capture_next_command_template' -Default '')
    measurement_session_measurement_capture_next_status_command_template = [string](Get-PayloadValue -Payload $MeasurementSessionPayload -Name 'measurement_capture_next_status_command_template' -Default '')
    measurement_capture_plan_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_plan_contract']) { '' } else { [string]$Payload.measurement_capture_plan_contract }
    measurement_capture_runbook_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_runbook_contract']) { '' } else { [string]$Payload.measurement_capture_runbook_contract }
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
    measurement_capture_next_command_kind = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_next_command_kind']) { '' } else { [string]$Payload.measurement_capture_next_command_kind }
    measurement_capture_next_command_template = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_next_command_template']) { '' } else { [string]$Payload.measurement_capture_next_command_template }
    measurement_capture_next_status_command_template = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['measurement_capture_next_status_command_template']) { '' } else { [string]$Payload.measurement_capture_next_status_command_template }
    mockup_capture_plan_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_plan_contract']) { '' } else { [string]$Payload.mockup_capture_plan_contract }
    mockup_capture_plan_status_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_plan_status_contract']) { '' } else { [string]$Payload.mockup_capture_plan_status_contract }
    mockup_capture_summary_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_summary_contract']) { '' } else { [string]$Payload.mockup_capture_summary_contract }
    mockup_capture_runbook_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_runbook_contract']) { '' } else { [string]$Payload.mockup_capture_runbook_contract }
    mockup_capture_plan_not_completion_evidence = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_capture_plan_not_completion_evidence']) { $false } else { [bool]$Payload.mockup_capture_plan_not_completion_evidence }
    next_required_mockup_input = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['next_required_mockup_input']) { '' } else { [string]$Payload.next_required_mockup_input }
    mockup_input_template_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_input_template_path']) { '' } else { [string]$Payload.mockup_input_template_path }
    mockup_record_initializer_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_record_initializer_path']) { '' } else { [string]$Payload.mockup_record_initializer_path }
    mockup_working_record_name_pattern = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mockup_working_record_name_pattern']) { '' } else { [string]$Payload.mockup_working_record_name_pattern }
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
    mockup_capture_first_blocking_group_missing_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'mockup_capture_first_blocking_group_missing_fields')
    mockup_capture_first_blocking_group_invalid_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'mockup_capture_first_blocking_group_invalid_fields')
    mockup_capture_first_blocking_group_blocking_signals = @(Get-PayloadArrayProperty -Payload $Payload -Name 'mockup_capture_first_blocking_group_blocking_signals')
    mannequin_capture_plan_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_plan_contract']) { '' } else { [string]$Payload.mannequin_capture_plan_contract }
    mannequin_capture_plan_status_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_plan_status_contract']) { '' } else { [string]$Payload.mannequin_capture_plan_status_contract }
    mannequin_capture_summary_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_summary_contract']) { '' } else { [string]$Payload.mannequin_capture_summary_contract }
    mannequin_capture_runbook_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_runbook_contract']) { '' } else { [string]$Payload.mannequin_capture_runbook_contract }
    mannequin_capture_plan_not_completion_evidence = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_capture_plan_not_completion_evidence']) { $false } else { [bool]$Payload.mannequin_capture_plan_not_completion_evidence }
    next_required_mannequin_input = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['next_required_mannequin_input']) { '' } else { [string]$Payload.next_required_mannequin_input }
    mannequin_input_template_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_input_template_path']) { '' } else { [string]$Payload.mannequin_input_template_path }
    mannequin_record_initializer_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_record_initializer_path']) { '' } else { [string]$Payload.mannequin_record_initializer_path }
    mannequin_working_record_name_pattern = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['mannequin_working_record_name_pattern']) { '' } else { [string]$Payload.mannequin_working_record_name_pattern }
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
    mannequin_capture_first_blocking_group_missing_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'mannequin_capture_first_blocking_group_missing_fields')
    mannequin_capture_first_blocking_group_invalid_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'mannequin_capture_first_blocking_group_invalid_fields')
    mannequin_capture_first_blocking_group_blocking_signals = @(Get-PayloadArrayProperty -Payload $Payload -Name 'mannequin_capture_first_blocking_group_blocking_signals')
    static_fit_capture_plan_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_plan_contract']) { '' } else { [string]$Payload.static_fit_capture_plan_contract }
    static_fit_capture_plan_status_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_plan_status_contract']) { '' } else { [string]$Payload.static_fit_capture_plan_status_contract }
    static_fit_capture_summary_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_summary_contract']) { '' } else { [string]$Payload.static_fit_capture_summary_contract }
    static_fit_capture_runbook_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_runbook_contract']) { '' } else { [string]$Payload.static_fit_capture_runbook_contract }
    static_fit_capture_plan_not_completion_evidence = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_capture_plan_not_completion_evidence']) { $false } else { [bool]$Payload.static_fit_capture_plan_not_completion_evidence }
    next_required_static_fit_input = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['next_required_static_fit_input']) { '' } else { [string]$Payload.next_required_static_fit_input }
    static_fit_input_template_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_input_template_path']) { '' } else { [string]$Payload.static_fit_input_template_path }
    static_fit_record_initializer_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_record_initializer_path']) { '' } else { [string]$Payload.static_fit_record_initializer_path }
    static_fit_working_record_name_pattern = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['static_fit_working_record_name_pattern']) { '' } else { [string]$Payload.static_fit_working_record_name_pattern }
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
    static_fit_capture_first_blocking_group_missing_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'static_fit_capture_first_blocking_group_missing_fields')
    static_fit_capture_first_blocking_group_invalid_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'static_fit_capture_first_blocking_group_invalid_fields')
    static_fit_capture_first_blocking_group_blocking_signals = @(Get-PayloadArrayProperty -Payload $Payload -Name 'static_fit_capture_first_blocking_group_blocking_signals')
    movement_capture_plan_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['movement_capture_plan_contract']) { '' } else { [string]$Payload.movement_capture_plan_contract }
    movement_capture_plan_status_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['movement_capture_plan_status_contract']) { '' } else { [string]$Payload.movement_capture_plan_status_contract }
    movement_capture_summary_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['movement_capture_summary_contract']) { '' } else { [string]$Payload.movement_capture_summary_contract }
    movement_capture_runbook_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['movement_capture_runbook_contract']) { '' } else { [string]$Payload.movement_capture_runbook_contract }
    movement_capture_plan_not_completion_evidence = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['movement_capture_plan_not_completion_evidence']) { $false } else { [bool]$Payload.movement_capture_plan_not_completion_evidence }
    next_required_movement_input = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['next_required_movement_input']) { '' } else { [string]$Payload.next_required_movement_input }
    movement_input_template_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['movement_input_template_path']) { '' } else { [string]$Payload.movement_input_template_path }
    movement_record_initializer_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['movement_record_initializer_path']) { '' } else { [string]$Payload.movement_record_initializer_path }
    movement_working_record_name_pattern = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['movement_working_record_name_pattern']) { '' } else { [string]$Payload.movement_working_record_name_pattern }
    movement_capture_plan = @(Get-PayloadObjectArrayProperty -Payload $Payload -Name 'movement_capture_plan')
    movement_capture_plan_status = @(Get-PayloadObjectArrayProperty -Payload $Payload -Name 'movement_capture_plan_status')
    movement_capture_total_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['movement_capture_total_groups']) { 0 } else { [int]$Payload.movement_capture_total_groups }
    movement_capture_ready_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['movement_capture_ready_groups']) { 0 } else { [int]$Payload.movement_capture_ready_groups }
    movement_capture_pending_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['movement_capture_pending_groups']) { 0 } else { [int]$Payload.movement_capture_pending_groups }
    movement_capture_invalid_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['movement_capture_invalid_groups']) { 0 } else { [int]$Payload.movement_capture_invalid_groups }
    movement_capture_failed_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['movement_capture_failed_groups']) { 0 } else { [int]$Payload.movement_capture_failed_groups }
    movement_capture_upstream_blocked_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['movement_capture_upstream_blocked_groups']) { 0 } else { [int]$Payload.movement_capture_upstream_blocked_groups }
    movement_capture_first_blocking_group_id = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['movement_capture_first_blocking_group_id']) { '' } else { [string]$Payload.movement_capture_first_blocking_group_id }
    movement_capture_first_blocking_group_status = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['movement_capture_first_blocking_group_status']) { '' } else { [string]$Payload.movement_capture_first_blocking_group_status }
    movement_capture_first_blocking_group_action = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['movement_capture_first_blocking_group_action']) { '' } else { [string]$Payload.movement_capture_first_blocking_group_action }
    movement_capture_first_blocking_group_missing_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'movement_capture_first_blocking_group_missing_fields')
    movement_capture_first_blocking_group_invalid_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'movement_capture_first_blocking_group_invalid_fields')
    movement_capture_first_blocking_group_blocking_signals = @(Get-PayloadArrayProperty -Payload $Payload -Name 'movement_capture_first_blocking_group_blocking_signals')
    release_cable_capture_plan_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['release_cable_capture_plan_contract']) { '' } else { [string]$Payload.release_cable_capture_plan_contract }
    release_cable_capture_plan_status_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['release_cable_capture_plan_status_contract']) { '' } else { [string]$Payload.release_cable_capture_plan_status_contract }
    release_cable_capture_summary_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['release_cable_capture_summary_contract']) { '' } else { [string]$Payload.release_cable_capture_summary_contract }
    release_cable_capture_runbook_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['release_cable_capture_runbook_contract']) { '' } else { [string]$Payload.release_cable_capture_runbook_contract }
    release_cable_capture_plan_not_completion_evidence = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['release_cable_capture_plan_not_completion_evidence']) { $false } else { [bool]$Payload.release_cable_capture_plan_not_completion_evidence }
    next_required_release_cable_input = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['next_required_release_cable_input']) { '' } else { [string]$Payload.next_required_release_cable_input }
    release_cable_input_template_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['release_cable_input_template_path']) { '' } else { [string]$Payload.release_cable_input_template_path }
    release_cable_record_initializer_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['release_cable_record_initializer_path']) { '' } else { [string]$Payload.release_cable_record_initializer_path }
    release_cable_working_record_name_pattern = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['release_cable_working_record_name_pattern']) { '' } else { [string]$Payload.release_cable_working_record_name_pattern }
    release_cable_capture_plan = @(Get-PayloadObjectArrayProperty -Payload $Payload -Name 'release_cable_capture_plan')
    release_cable_capture_plan_status = @(Get-PayloadObjectArrayProperty -Payload $Payload -Name 'release_cable_capture_plan_status')
    release_cable_capture_total_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['release_cable_capture_total_groups']) { 0 } else { [int]$Payload.release_cable_capture_total_groups }
    release_cable_capture_ready_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['release_cable_capture_ready_groups']) { 0 } else { [int]$Payload.release_cable_capture_ready_groups }
    release_cable_capture_pending_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['release_cable_capture_pending_groups']) { 0 } else { [int]$Payload.release_cable_capture_pending_groups }
    release_cable_capture_invalid_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['release_cable_capture_invalid_groups']) { 0 } else { [int]$Payload.release_cable_capture_invalid_groups }
    release_cable_capture_failed_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['release_cable_capture_failed_groups']) { 0 } else { [int]$Payload.release_cable_capture_failed_groups }
    release_cable_capture_upstream_blocked_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['release_cable_capture_upstream_blocked_groups']) { 0 } else { [int]$Payload.release_cable_capture_upstream_blocked_groups }
    release_cable_capture_first_blocking_group_id = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['release_cable_capture_first_blocking_group_id']) { '' } else { [string]$Payload.release_cable_capture_first_blocking_group_id }
    release_cable_capture_first_blocking_group_status = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['release_cable_capture_first_blocking_group_status']) { '' } else { [string]$Payload.release_cable_capture_first_blocking_group_status }
    release_cable_capture_first_blocking_group_action = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['release_cable_capture_first_blocking_group_action']) { '' } else { [string]$Payload.release_cable_capture_first_blocking_group_action }
    release_cable_capture_first_blocking_group_missing_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'release_cable_capture_first_blocking_group_missing_fields')
    release_cable_capture_first_blocking_group_invalid_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'release_cable_capture_first_blocking_group_invalid_fields')
    release_cable_capture_first_blocking_group_blocking_signals = @(Get-PayloadArrayProperty -Payload $Payload -Name 'release_cable_capture_first_blocking_group_blocking_signals')
    engineering_review_capture_plan_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['engineering_review_capture_plan_contract']) { '' } else { [string]$Payload.engineering_review_capture_plan_contract }
    engineering_review_capture_runbook_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['engineering_review_capture_runbook_contract']) { '' } else { [string]$Payload.engineering_review_capture_runbook_contract }
    engineering_review_capture_plan_status_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['engineering_review_capture_plan_status_contract']) { '' } else { [string]$Payload.engineering_review_capture_plan_status_contract }
    engineering_review_capture_summary_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['engineering_review_capture_summary_contract']) { '' } else { [string]$Payload.engineering_review_capture_summary_contract }
    engineering_review_capture_plan_not_completion_evidence = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['engineering_review_capture_plan_not_completion_evidence']) { $false } else { [bool]$Payload.engineering_review_capture_plan_not_completion_evidence }
    next_required_engineering_review_input = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['next_required_engineering_review_input']) { '' } else { [string]$Payload.next_required_engineering_review_input }
    engineering_review_input_template_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['engineering_review_input_template_path']) { '' } else { [string]$Payload.engineering_review_input_template_path }
    engineering_review_record_initializer_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['engineering_review_record_initializer_path']) { '' } else { [string]$Payload.engineering_review_record_initializer_path }
    engineering_review_working_record_name_pattern = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['engineering_review_working_record_name_pattern']) { '' } else { [string]$Payload.engineering_review_working_record_name_pattern }
    engineering_review_capture_plan = @(Get-PayloadObjectArrayProperty -Payload $Payload -Name 'engineering_review_capture_plan')
    engineering_review_capture_plan_status = @(Get-PayloadObjectArrayProperty -Payload $Payload -Name 'engineering_review_capture_plan_status')
    engineering_review_capture_total_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['engineering_review_capture_total_groups']) { 0 } else { [int]$Payload.engineering_review_capture_total_groups }
    engineering_review_capture_ready_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['engineering_review_capture_ready_groups']) { 0 } else { [int]$Payload.engineering_review_capture_ready_groups }
    engineering_review_capture_pending_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['engineering_review_capture_pending_groups']) { 0 } else { [int]$Payload.engineering_review_capture_pending_groups }
    engineering_review_capture_invalid_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['engineering_review_capture_invalid_groups']) { 0 } else { [int]$Payload.engineering_review_capture_invalid_groups }
    engineering_review_capture_failed_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['engineering_review_capture_failed_groups']) { 0 } else { [int]$Payload.engineering_review_capture_failed_groups }
    engineering_review_capture_upstream_blocked_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['engineering_review_capture_upstream_blocked_groups']) { 0 } else { [int]$Payload.engineering_review_capture_upstream_blocked_groups }
    engineering_review_capture_first_blocking_group_id = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['engineering_review_capture_first_blocking_group_id']) { '' } else { [string]$Payload.engineering_review_capture_first_blocking_group_id }
    engineering_review_capture_first_blocking_group_status = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['engineering_review_capture_first_blocking_group_status']) { '' } else { [string]$Payload.engineering_review_capture_first_blocking_group_status }
    engineering_review_capture_first_blocking_group_action = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['engineering_review_capture_first_blocking_group_action']) { '' } else { [string]$Payload.engineering_review_capture_first_blocking_group_action }
    engineering_review_capture_first_blocking_group_missing_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'engineering_review_capture_first_blocking_group_missing_fields')
    engineering_review_capture_first_blocking_group_invalid_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'engineering_review_capture_first_blocking_group_invalid_fields')
    engineering_review_capture_first_blocking_group_blocking_signals = @(Get-PayloadArrayProperty -Payload $Payload -Name 'engineering_review_capture_first_blocking_group_blocking_signals')
    final_physical_decision_plan_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_physical_decision_plan_contract']) { '' } else { [string]$Payload.final_physical_decision_plan_contract }
    final_physical_decision_runbook_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_physical_decision_runbook_contract']) { '' } else { [string]$Payload.final_physical_decision_runbook_contract }
    final_physical_decision_plan_status_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_physical_decision_plan_status_contract']) { '' } else { [string]$Payload.final_physical_decision_plan_status_contract }
    final_physical_decision_summary_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_physical_decision_summary_contract']) { '' } else { [string]$Payload.final_physical_decision_summary_contract }
    final_physical_decision_plan_not_completion_evidence = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_physical_decision_plan_not_completion_evidence']) { $false } else { [bool]$Payload.final_physical_decision_plan_not_completion_evidence }
    next_required_final_physical_input = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['next_required_final_physical_input']) { '' } else { [string]$Payload.next_required_final_physical_input }
    final_decision_input_template_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_decision_input_template_path']) { '' } else { [string]$Payload.final_decision_input_template_path }
    final_decision_record_initializer_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_decision_record_initializer_path']) { '' } else { [string]$Payload.final_decision_record_initializer_path }
    final_decision_working_record_name_pattern = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_decision_working_record_name_pattern']) { '' } else { [string]$Payload.final_decision_working_record_name_pattern }
    final_physical_gate_record_name_pattern = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_physical_gate_record_name_pattern']) { '' } else { [string]$Payload.final_physical_gate_record_name_pattern }
    final_physical_decision_plan = @(Get-PayloadObjectArrayProperty -Payload $Payload -Name 'final_physical_decision_plan')
    final_physical_decision_plan_status = @(Get-PayloadObjectArrayProperty -Payload $Payload -Name 'final_physical_decision_plan_status')
    final_physical_decision_total_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_physical_decision_total_groups']) { 0 } else { [int]$Payload.final_physical_decision_total_groups }
    final_physical_decision_ready_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_physical_decision_ready_groups']) { 0 } else { [int]$Payload.final_physical_decision_ready_groups }
    final_physical_decision_pending_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_physical_decision_pending_groups']) { 0 } else { [int]$Payload.final_physical_decision_pending_groups }
    final_physical_decision_invalid_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_physical_decision_invalid_groups']) { 0 } else { [int]$Payload.final_physical_decision_invalid_groups }
    final_physical_decision_failed_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_physical_decision_failed_groups']) { 0 } else { [int]$Payload.final_physical_decision_failed_groups }
    final_physical_decision_blocked_groups = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_physical_decision_blocked_groups']) { 0 } else { [int]$Payload.final_physical_decision_blocked_groups }
    final_physical_decision_first_blocking_group_id = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_physical_decision_first_blocking_group_id']) { '' } else { [string]$Payload.final_physical_decision_first_blocking_group_id }
    final_physical_decision_first_blocking_group_status = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_physical_decision_first_blocking_group_status']) { '' } else { [string]$Payload.final_physical_decision_first_blocking_group_status }
    final_physical_decision_first_blocking_group_action = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_physical_decision_first_blocking_group_action']) { '' } else { [string]$Payload.final_physical_decision_first_blocking_group_action }
    final_physical_decision_first_blocking_group_missing_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'final_physical_decision_first_blocking_group_missing_fields')
    final_physical_decision_first_blocking_group_invalid_fields = @(Get-PayloadArrayProperty -Payload $Payload -Name 'final_physical_decision_first_blocking_group_invalid_fields')
    final_physical_decision_first_blocking_group_blocking_signals = @(Get-PayloadArrayProperty -Payload $Payload -Name 'final_physical_decision_first_blocking_group_blocking_signals')
    final_decision_record_ready = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_decision_record_ready']) { $false } else { [bool]$Payload.final_decision_record_ready }
    final_decision_record_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_decision_record_contract']) { '' } else { [string]$Payload.final_decision_record_contract }
    final_decision_record_runbook_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_decision_record_runbook_contract']) { '' } else { [string]$Payload.final_decision_record_runbook_contract }
    ledger_completion_review_ready = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['ledger_completion_review_ready']) { $false } else { [bool]$Payload.ledger_completion_review_ready }
    decision_lock_violations = @(Get-PayloadArrayProperty -Payload $Payload -Name 'decision_lock_violations')
    completion_decision_violations = @(Get-PayloadArrayProperty -Payload $Payload -Name 'completion_decision_violations')
    saved_final_physical_gate_record_status = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['saved_final_physical_gate_record_status']) { '' } else { [string]$Payload.saved_final_physical_gate_record_status }
    next_required_final_decision_input = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['next_required_final_decision_input']) { '' } else { [string]$Payload.next_required_final_decision_input }
    final_decision_gate_status = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_decision_gate_status']) { '' } else { [string]$Payload.final_decision_gate_status }
    final_decision_record_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['final_decision_record_path']) { '' } else { [string]$Payload.final_decision_record_path }
    ledger_entry_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['ledger_entry_path']) { '' } else { [string]$Payload.ledger_entry_path }
    ledger_entry_exists = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['ledger_entry_exists']) { $false } else { [bool]$Payload.ledger_entry_exists }
    ledger_entry_read_ok = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['ledger_entry_read_ok']) { $false } else { [bool]$Payload.ledger_entry_read_ok }
    ledger_entry_review_ready = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['ledger_entry_review_ready']) { $false } else { [bool]$Payload.ledger_entry_review_ready }
    ledger_entry_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['ledger_entry_contract']) { '' } else { [string]$Payload.ledger_entry_contract }
    completion_ledger_handoff_runbook_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['completion_ledger_handoff_runbook_contract']) { '' } else { [string]$Payload.completion_ledger_handoff_runbook_contract }
    completion_ledger_handoff_template_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['completion_ledger_handoff_template_path']) { '' } else { [string]$Payload.completion_ledger_handoff_template_path }
    completion_ledger_handoff_initializer_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['completion_ledger_handoff_initializer_path']) { '' } else { [string]$Payload.completion_ledger_handoff_initializer_path }
    completion_ledger_handoff_working_record_name_pattern = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['completion_ledger_handoff_working_record_name_pattern']) { '' } else { [string]$Payload.completion_ledger_handoff_working_record_name_pattern }
    next_required_ledger_input = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['next_required_ledger_input']) { '' } else { [string]$Payload.next_required_ledger_input }
    completion_ledger_gate_status = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['completion_ledger_gate_status']) { '' } else { [string]$Payload.completion_ledger_gate_status }
    completion_ledger_gate_exit_code = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['completion_ledger_gate_exit_code']) { 0 } else { [int]$Payload.completion_ledger_gate_exit_code }
    completion_ledger_gate_parse_ok = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['completion_ledger_gate_parse_ok']) { $false } else { [bool]$Payload.completion_ledger_gate_parse_ok }
    completion_ledger_handoff_ready = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['completion_ledger_handoff_ready']) { $false } else { [bool]$Payload.completion_ledger_handoff_ready }
    completion_ledger_handoff_failed = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['completion_ledger_handoff_failed']) { $false } else { [bool]$Payload.completion_ledger_handoff_failed }
    candidate_ledger_entry_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['candidate_ledger_entry_path']) { '' } else { [string]$Payload.candidate_ledger_entry_path }
    candidate_ledger_heading = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['candidate_ledger_heading']) { '' } else { [string]$Payload.candidate_ledger_heading }
    completion_ledger_path = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['completion_ledger_path']) { '' } else { [string]$Payload.completion_ledger_path }
    completion_ledger_exists = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['completion_ledger_exists']) { $false } else { [bool]$Payload.completion_ledger_exists }
    completion_ledger_read_ok = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['completion_ledger_read_ok']) { $false } else { [bool]$Payload.completion_ledger_read_ok }
    ledger_update_section_found = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['ledger_update_section_found']) { $false } else { [bool]$Payload.ledger_update_section_found }
    ledger_update_review_ready = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['ledger_update_review_ready']) { $false } else { [bool]$Payload.ledger_update_review_ready }
    completion_ledger_update_guard_contract = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['completion_ledger_update_guard_contract']) { '' } else { [string]$Payload.completion_ledger_update_guard_contract }
    next_required_completion_ledger_update_input = if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties['next_required_completion_ledger_update_input']) { '' } else { [string]$Payload.next_required_completion_ledger_update_input }
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

function New-FirstBlockingUpdateHint {
  param(
    [string]$GateId,
    [bool]$GateFailed,
    [object]$GateDetails
  )

  $ToolPath = ''
  $CommandTemplate = ''
  $Contract = ''

  if ($GateFailed) {
    if ($GateId -eq 'measurement_intake') {
      $Contract = [string](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_update_contract')
    }
    if ([string]::IsNullOrWhiteSpace($Contract)) {
      $Contract = 'Stop the FR-017 evidence chain and resolve the failed safety, validation, or redesign condition before creating downstream evidence records.'
    }
    return [ordered]@{
      tool_path = ''
      command_template = ''
      contract = $Contract
    }
  }

  switch ($GateId) {
    'measurement_intake' {
      $ToolPath = [string](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_update_tool_path')
      $CommandTemplate = [string](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_update_command_template')
      $Contract = [string](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_update_contract')
    }
    'mockup_readiness' {
      $ToolPath = [string](Get-DetailsValue -Details $GateDetails -Name 'mockup_record_initializer_path')
      $CommandTemplate = '.\scripts\fr017-new-mockup-record.ps1 -Mode Create -OutputPath <mockup-record.json> -MeasurementPath <measurement-record.json>'
      $Contract = [string](Get-DetailsValue -Details $GateDetails -Name 'mockup_capture_runbook_contract')
    }
    'mannequin_interface' {
      $ToolPath = [string](Get-DetailsValue -Details $GateDetails -Name 'mannequin_record_initializer_path')
      $CommandTemplate = '.\scripts\fr017-new-mannequin-interface-record.ps1 -Mode Create -OutputPath <mannequin-interface-record.json> -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json>'
      $Contract = [string](Get-DetailsValue -Details $GateDetails -Name 'mannequin_capture_runbook_contract')
    }
    'pilot_static_fit' {
      $ToolPath = [string](Get-DetailsValue -Details $GateDetails -Name 'static_fit_record_initializer_path')
      $CommandTemplate = '.\scripts\fr017-new-pilot-static-fit-record.ps1 -Mode Create -OutputPath <pilot-static-fit-record.json> -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-interface-record.json>'
      $Contract = [string](Get-DetailsValue -Details $GateDetails -Name 'static_fit_capture_runbook_contract')
    }
    'pilot_movement' {
      $ToolPath = [string](Get-DetailsValue -Details $GateDetails -Name 'movement_record_initializer_path')
      $CommandTemplate = '.\scripts\fr017-new-pilot-movement-record.ps1 -Mode Create -OutputPath <pilot-movement-record.json> -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-interface-record.json> -StaticFitPath <pilot-static-fit-record.json>'
      $Contract = [string](Get-DetailsValue -Details $GateDetails -Name 'movement_capture_runbook_contract')
    }
    'quick_release_cable_snag' {
      $ToolPath = [string](Get-DetailsValue -Details $GateDetails -Name 'release_cable_record_initializer_path')
      $CommandTemplate = '.\scripts\fr017-new-release-cable-record.ps1 -Mode Create -OutputPath <release-cable-record.json> -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-interface-record.json> -StaticFitPath <pilot-static-fit-record.json> -MovementPath <pilot-movement-record.json>'
      $Contract = [string](Get-DetailsValue -Details $GateDetails -Name 'release_cable_capture_runbook_contract')
    }
    'engineering_review' {
      $ToolPath = [string](Get-DetailsValue -Details $GateDetails -Name 'engineering_review_record_initializer_path')
      $CommandTemplate = '.\scripts\fr017-new-engineering-review-record.ps1 -Mode Create -OutputPath <engineering-review-record.json> -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-interface-record.json> -StaticFitPath <pilot-static-fit-record.json> -MovementPath <pilot-movement-record.json> -ReleaseCablePath <release-cable-record.json>'
      $Contract = [string](Get-DetailsValue -Details $GateDetails -Name 'engineering_review_capture_runbook_contract')
    }
    'final_decision_record' {
      $ToolPath = [string](Get-DetailsValue -Details $GateDetails -Name 'final_decision_record_initializer_path')
      $CommandTemplate = '.\scripts\fr017-new-final-decision-record.ps1 -Mode Create -OutputPath <final-decision-record.json> -FinalPhysicalGateRecordOutputPath <final-physical-gate-record.json> -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-interface-record.json> -StaticFitPath <pilot-static-fit-record.json> -MovementPath <pilot-movement-record.json> -ReleaseCablePath <release-cable-record.json> -EngineeringReviewPath <engineering-review-record.json>'
      $Contract = [string](Get-DetailsValue -Details $GateDetails -Name 'final_decision_record_runbook_contract')
    }
    'completion_ledger' {
      $ToolPath = [string](Get-DetailsValue -Details $GateDetails -Name 'completion_ledger_handoff_initializer_path')
      $CommandTemplate = '.\scripts\fr017-new-completion-ledger-handoff.ps1 -Mode Create -OutputPath <completion-ledger-handoff.md> -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-interface-record.json> -StaticFitPath <pilot-static-fit-record.json> -MovementPath <pilot-movement-record.json> -ReleaseCablePath <release-cable-record.json> -EngineeringReviewPath <engineering-review-record.json> -FinalDecisionPath <final-decision-record.json>'
      $Contract = [string](Get-DetailsValue -Details $GateDetails -Name 'completion_ledger_handoff_runbook_contract')
    }
    'completion_ledger_update' {
      $ToolPath = Join-Path $RepoRoot 'scripts\fr017-completion-ledger-update-gate.ps1'
      $CommandTemplate = '.\scripts\fr017-completion-ledger-update-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-interface-record.json> -StaticFitPath <pilot-static-fit-record.json> -MovementPath <pilot-movement-record.json> -ReleaseCablePath <release-cable-record.json> -EngineeringReviewPath <engineering-review-record.json> -FinalDecisionPath <final-decision-record.json> -LedgerEntryPath <completion-ledger-handoff.md> -CompletionLedgerPath <COMPLETION_LEDGER.md>'
      $Contract = [string](Get-DetailsValue -Details $GateDetails -Name 'completion_ledger_update_guard_contract')
    }
  }

  if ([string]::IsNullOrWhiteSpace($ToolPath)) {
    $CommandTemplate = ''
  }

  if ([string]::IsNullOrWhiteSpace($Contract) -and -not [string]::IsNullOrWhiteSpace($CommandTemplate)) {
    $Contract = 'Operator input tooling only; this hint creates or updates a pending evidence record and does not mark physical validation complete.'
  }

  return [ordered]@{
    tool_path = $ToolPath
    command_template = $CommandTemplate
    contract = $Contract
  }
}

function Get-FirstNonEmptyDetailsValue {
  param(
    [object]$Details,
    [string[]]$Names
  )

  foreach ($Name in $Names) {
    $Value = [string](Get-DetailsValue -Details $Details -Name $Name)
    if (-not [string]::IsNullOrWhiteSpace($Value)) {
      return $Value
    }
  }
  return ''
}

function Get-FirstNonEmptyDetailsArray {
  param(
    [object]$Details,
    [string[]]$Names
  )

  foreach ($Name in $Names) {
    $Values = @(Get-DetailsArrayValue -Details $Details -Name $Name)
    if ($Values.Count -gt 0) {
      return @($Values)
    }
  }
  return @()
}

function New-EvidenceChainSummary {
  param([System.Collections.IDictionary]$StatusPayload)

  $Details = $StatusPayload['first_blocking_details']
  $CaptureGroupId = Get-FirstNonEmptyDetailsValue -Details $Details -Names @(
    'measurement_session_current_group_id',
    'measurement_capture_first_blocking_group_id',
    'mockup_capture_first_blocking_group_id',
    'mannequin_capture_first_blocking_group_id',
    'static_fit_capture_first_blocking_group_id',
    'movement_capture_first_blocking_group_id',
    'release_cable_capture_first_blocking_group_id',
    'engineering_review_capture_first_blocking_group_id',
    'final_physical_decision_first_blocking_group_id'
  )
  $CaptureGroupStatus = Get-FirstNonEmptyDetailsValue -Details $Details -Names @(
    'measurement_capture_first_blocking_group_status',
    'mockup_capture_first_blocking_group_status',
    'mannequin_capture_first_blocking_group_status',
    'static_fit_capture_first_blocking_group_status',
    'movement_capture_first_blocking_group_status',
    'release_cable_capture_first_blocking_group_status',
    'engineering_review_capture_first_blocking_group_status',
    'final_physical_decision_first_blocking_group_status'
  )
  $CaptureGroupAction = Get-FirstNonEmptyDetailsValue -Details $Details -Names @(
    'measurement_session_current_group_required_action',
    'measurement_capture_first_blocking_group_action',
    'mockup_capture_first_blocking_group_action',
    'mannequin_capture_first_blocking_group_action',
    'static_fit_capture_first_blocking_group_action',
    'movement_capture_first_blocking_group_action',
    'release_cable_capture_first_blocking_group_action',
    'engineering_review_capture_first_blocking_group_action',
    'final_physical_decision_first_blocking_group_action'
  )
  $CaptureGroupMissingFields = @(Get-FirstNonEmptyDetailsArray -Details $Details -Names @(
    'measurement_session_current_group_missing_fields',
    'mockup_capture_first_blocking_group_missing_fields',
    'mannequin_capture_first_blocking_group_missing_fields',
    'static_fit_capture_first_blocking_group_missing_fields',
    'movement_capture_first_blocking_group_missing_fields',
    'release_cable_capture_first_blocking_group_missing_fields',
    'engineering_review_capture_first_blocking_group_missing_fields',
    'final_physical_decision_first_blocking_group_missing_fields',
    'missing_fields',
    'measurement_missing_fields',
    'mockup_missing_fields'
  ))
  $CaptureGroupInvalidFields = @(Get-FirstNonEmptyDetailsArray -Details $Details -Names @(
    'measurement_session_current_group_invalid_fields',
    'mockup_capture_first_blocking_group_invalid_fields',
    'mannequin_capture_first_blocking_group_invalid_fields',
    'static_fit_capture_first_blocking_group_invalid_fields',
    'movement_capture_first_blocking_group_invalid_fields',
    'release_cable_capture_first_blocking_group_invalid_fields',
    'engineering_review_capture_first_blocking_group_invalid_fields',
    'final_physical_decision_first_blocking_group_invalid_fields',
    'invalid_fields',
    'measurement_invalid_fields',
    'mockup_invalid_fields'
  ))
  $CaptureGroupBlockingSignals = @(Get-FirstNonEmptyDetailsArray -Details $Details -Names @(
    'measurement_session_current_group_blocking_signals',
    'mockup_capture_first_blocking_group_blocking_signals',
    'mannequin_capture_first_blocking_group_blocking_signals',
    'static_fit_capture_first_blocking_group_blocking_signals',
    'movement_capture_first_blocking_group_blocking_signals',
    'release_cable_capture_first_blocking_group_blocking_signals',
    'engineering_review_capture_first_blocking_group_blocking_signals',
    'final_physical_decision_first_blocking_group_blocking_signals',
    'safety_blockers',
    'symptom_blockers',
    'prohibited_clearance_flags',
    'failed_reasons'
  ))
  $CaptureGroupUpdateRequiredInputFields = @(Get-FirstNonEmptyDetailsArray -Details $Details -Names @(
    'measurement_session_current_group_update_required_input_fields'
  ))
  $OperatorInputHint = Get-FirstNonEmptyDetailsValue -Details $Details -Names @(
    'next_required_physical_input',
    'next_required_mockup_input',
    'next_required_mannequin_input',
    'next_required_static_fit_input',
    'next_required_movement_input',
    'next_required_release_cable_input',
    'next_required_engineering_review_input',
    'next_required_final_physical_input',
    'next_required_final_decision_input',
    'next_required_ledger_input',
    'next_required_completion_ledger_update_input'
  )
  $CaptureNextCommandKind = Get-FirstNonEmptyDetailsValue -Details $Details -Names @(
    'measurement_session_measurement_capture_next_command_kind',
    'measurement_capture_next_command_kind'
  )
  $CaptureNextCommandTemplate = Get-FirstNonEmptyDetailsValue -Details $Details -Names @(
    'measurement_session_measurement_capture_next_command_template',
    'measurement_capture_next_command_template'
  )
  $CaptureNextStatusCommandTemplate = Get-FirstNonEmptyDetailsValue -Details $Details -Names @(
    'measurement_session_measurement_capture_next_status_command_template',
    'measurement_capture_next_status_command_template'
  )

  return [ordered]@{
    kind = 'francis.fr017.evidence_chain_summary'
    mode = 'Summary'
    source_kind = [string]$StatusPayload['kind']
    source_mode = 'Status'
    status = [string]$StatusPayload['status']
    evidence_chain_decision_ready = [bool]$StatusPayload['evidence_chain_decision_ready']
    ledger_completion_review_ready = [bool]$StatusPayload['ledger_completion_review_ready']
    completion_ledger_handoff_ready = [bool]$StatusPayload['completion_ledger_handoff_ready']
    completion_ledger_update_review_ready = [bool]$StatusPayload['completion_ledger_update_review_ready']
    physical_validation_complete = [bool]$StatusPayload['physical_validation_complete']
    stage17_completion_claim_allowed = [bool]$StatusPayload['stage17_completion_claim_allowed']
    powered_or_frame_coupled_testing_cleared = [bool]$StatusPayload['powered_or_frame_coupled_testing_cleared']
    fr018_implementation_cleared = [bool]$StatusPayload['fr018_implementation_cleared']
    read_only_contract = [bool]$StatusPayload['read_only_contract']
    writes_repo = [bool]$StatusPayload['writes_repo']
    writes_data = [bool]$StatusPayload['writes_data']
    grants_execution_authority = [bool]$StatusPayload['grants_execution_authority']
    grants_mutation_authority = [bool]$StatusPayload['grants_mutation_authority']
    first_blocking_gate = [string]$StatusPayload['first_blocking_gate']
    first_blocking_status = [string]$StatusPayload['first_blocking_status']
    first_blocking_capture_group_id = $CaptureGroupId
    first_blocking_capture_group_status = $CaptureGroupStatus
    first_blocking_capture_group_required_action = $CaptureGroupAction
    first_blocking_capture_group_missing_field_count = $CaptureGroupMissingFields.Count
    first_blocking_capture_group_missing_fields = @($CaptureGroupMissingFields)
    first_blocking_capture_group_invalid_field_count = $CaptureGroupInvalidFields.Count
    first_blocking_capture_group_invalid_fields = @($CaptureGroupInvalidFields)
    first_blocking_capture_group_blocking_signal_count = $CaptureGroupBlockingSignals.Count
    first_blocking_capture_group_blocking_signals = @($CaptureGroupBlockingSignals)
    first_blocking_capture_group_update_required_input_count = $CaptureGroupUpdateRequiredInputFields.Count
    first_blocking_capture_group_update_required_input_fields = @($CaptureGroupUpdateRequiredInputFields)
    first_blocking_capture_next_command_kind = $CaptureNextCommandKind
    first_blocking_capture_next_command_template = $CaptureNextCommandTemplate
    first_blocking_capture_next_status_command_template = $CaptureNextStatusCommandTemplate
    next_required_input = [string]$StatusPayload['next_required_input']
    next_command = [string]$StatusPayload['next_command']
    operator_input_hint = $OperatorInputHint
    first_blocking_preflight_tool_path = [string]$StatusPayload['first_blocking_preflight_tool_path']
    first_blocking_preflight_command_template = [string]$StatusPayload['first_blocking_preflight_command_template']
    first_blocking_preflight_status = [string]$StatusPayload['first_blocking_preflight_status']
    first_blocking_preflight_parse_ok = [bool]$StatusPayload['first_blocking_preflight_parse_ok']
    first_blocking_preflight_read_only_contract = [bool]$StatusPayload['first_blocking_preflight_read_only_contract']
    first_blocking_preflight_template_exists = [bool]$StatusPayload['first_blocking_preflight_template_exists']
    first_blocking_preflight_template_parse_ok = [bool]$StatusPayload['first_blocking_preflight_template_parse_ok']
    first_blocking_preflight_candidate_output_path_ready = [bool]$StatusPayload['first_blocking_preflight_candidate_output_path_ready']
    first_blocking_preflight_output_path = [string]$StatusPayload['first_blocking_preflight_output_path']
    first_blocking_preflight_output_exists = [bool]$StatusPayload['first_blocking_preflight_output_exists']
    first_blocking_preflight_output_parent_exists = [bool]$StatusPayload['first_blocking_preflight_output_parent_exists']
    first_blocking_preflight_wrote_file = [bool]$StatusPayload['first_blocking_preflight_wrote_file']
    first_blocking_preflight_physical_validation_complete = [bool]$StatusPayload['first_blocking_preflight_physical_validation_complete']
    first_blocking_preflight_stage17_completion_claim_allowed = [bool]$StatusPayload['first_blocking_preflight_stage17_completion_claim_allowed']
    first_blocking_preflight_fr018_implementation_cleared = [bool]$StatusPayload['first_blocking_preflight_fr018_implementation_cleared']
    first_blocking_update_tool_path = [string]$StatusPayload['first_blocking_update_tool_path']
    first_blocking_update_command_template = [string]$StatusPayload['first_blocking_update_command_template']
    gates_ran = [int]$StatusPayload['gates_ran']
    gate_count = [int]$StatusPayload['gate_count']
    omitted_full_status_fields = @('first_blocking_details', 'gate_results')
    no_fake_validation_lock = [string]$StatusPayload['no_fake_validation_lock']
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

$FinalDecisionArgs = New-Object System.Collections.Generic.List[string]
$FinalDecisionArgs.Add('-Mode') | Out-Null
$FinalDecisionArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $FinalDecisionArgs -Name '-ManifestPath' -Value $ManifestPath
Add-OptionalArg -Target $FinalDecisionArgs -Name '-MeasurementPath' -Value $MeasurementPath
Add-OptionalArg -Target $FinalDecisionArgs -Name '-MockupPath' -Value $MockupPath
Add-OptionalArg -Target $FinalDecisionArgs -Name '-MannequinPath' -Value $MannequinPath
Add-OptionalArg -Target $FinalDecisionArgs -Name '-StaticFitPath' -Value $StaticFitPath
Add-OptionalArg -Target $FinalDecisionArgs -Name '-MovementPath' -Value $MovementPath
Add-OptionalArg -Target $FinalDecisionArgs -Name '-ReleaseCablePath' -Value $ReleaseCablePath
Add-OptionalArg -Target $FinalDecisionArgs -Name '-EngineeringReviewPath' -Value $EngineeringReviewPath
Add-OptionalArg -Target $FinalDecisionArgs -Name '-FinalDecisionPath' -Value $FinalDecisionPath

$CompletionLedgerArgs = New-Object System.Collections.Generic.List[string]
$CompletionLedgerArgs.Add('-Mode') | Out-Null
$CompletionLedgerArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-ManifestPath' -Value $ManifestPath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-MeasurementPath' -Value $MeasurementPath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-MockupPath' -Value $MockupPath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-MannequinPath' -Value $MannequinPath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-StaticFitPath' -Value $StaticFitPath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-MovementPath' -Value $MovementPath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-ReleaseCablePath' -Value $ReleaseCablePath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-EngineeringReviewPath' -Value $EngineeringReviewPath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-FinalDecisionPath' -Value $FinalDecisionPath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-LedgerEntryPath' -Value $LedgerEntryPath

$CompletionLedgerUpdateArgs = New-Object System.Collections.Generic.List[string]
$CompletionLedgerUpdateArgs.Add('-Mode') | Out-Null
$CompletionLedgerUpdateArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $CompletionLedgerUpdateArgs -Name '-ManifestPath' -Value $ManifestPath
Add-OptionalArg -Target $CompletionLedgerUpdateArgs -Name '-MeasurementPath' -Value $MeasurementPath
Add-OptionalArg -Target $CompletionLedgerUpdateArgs -Name '-MockupPath' -Value $MockupPath
Add-OptionalArg -Target $CompletionLedgerUpdateArgs -Name '-MannequinPath' -Value $MannequinPath
Add-OptionalArg -Target $CompletionLedgerUpdateArgs -Name '-StaticFitPath' -Value $StaticFitPath
Add-OptionalArg -Target $CompletionLedgerUpdateArgs -Name '-MovementPath' -Value $MovementPath
Add-OptionalArg -Target $CompletionLedgerUpdateArgs -Name '-ReleaseCablePath' -Value $ReleaseCablePath
Add-OptionalArg -Target $CompletionLedgerUpdateArgs -Name '-EngineeringReviewPath' -Value $EngineeringReviewPath
Add-OptionalArg -Target $CompletionLedgerUpdateArgs -Name '-FinalDecisionPath' -Value $FinalDecisionPath
Add-OptionalArg -Target $CompletionLedgerUpdateArgs -Name '-LedgerEntryPath' -Value $LedgerEntryPath
Add-OptionalArg -Target $CompletionLedgerUpdateArgs -Name '-CompletionLedgerPath' -Value $CompletionLedgerPath

$Gates = @(
  (New-GateDefinition -Id 'stage17_package' -ScriptName 'fr017-stage17-validation-gate.ps1' -ReadyStatus 'blocked_physical_validation' -NextRequiredInput 'FR-017-STAGE17-PACKAGE-MANIFEST.json' -NextCommand 'correct_FR-017_package_manifest_or_records' -Arguments $PackageArgs.ToArray()),
  (New-GateDefinition -Id 'measurement_intake' -ScriptName 'fr017-measurement-intake.ps1' -ReadyStatus 'ready_for_non_powered_mockup_patterning' -NextRequiredInput 'scripts/fr017-new-measurement-record.ps1 + FR-017-MEASUREMENT-CAPTURE-RUNBOOK.md + FR-017-MEASUREMENTS-INPUT-TEMPLATE.json' -NextCommand 'create_pending_measurement_record_then_capture_with_runbook_and_rerun_measurement_intake' -Arguments $MeasurementArgs.ToArray()),
  (New-GateDefinition -Id 'mockup_readiness' -ScriptName 'fr017-mockup-readiness-gate.ps1' -ReadyStatus 'ready_for_mannequin_interface_test' -NextRequiredInput 'scripts/fr017-new-mockup-record.ps1 + FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json' -NextCommand 'create_non_powered_mockup_record_then_rerun_mockup_readiness_gate' -Arguments $MockupArgs.ToArray()),
  (New-GateDefinition -Id 'mannequin_interface' -ScriptName 'fr017-mannequin-interface-gate.ps1' -ReadyStatus 'ready_for_pilot_static_fit_planning' -NextRequiredInput 'scripts/fr017-new-mannequin-interface-record.ps1 + FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json' -NextCommand 'create_non_powered_mannequin_interface_record_then_rerun_mannequin_interface_gate' -Arguments $MannequinArgs.ToArray()),
  (New-GateDefinition -Id 'pilot_static_fit' -ScriptName 'fr017-pilot-static-fit-gate.ps1' -ReadyStatus 'ready_for_pilot_movement_test_planning' -NextRequiredInput 'scripts/fr017-new-pilot-static-fit-record.ps1 + FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json' -NextCommand 'create_non_powered_pilot_static_fit_record_then_rerun_pilot_static_fit_gate' -Arguments $StaticFitArgs.ToArray()),
  (New-GateDefinition -Id 'pilot_movement' -ScriptName 'fr017-pilot-movement-gate.ps1' -ReadyStatus 'ready_for_quick_release_and_cable_snag_test_planning' -NextRequiredInput 'scripts/fr017-new-pilot-movement-record.ps1 + FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json' -NextCommand 'create_non_powered_pilot_movement_record_then_rerun_pilot_movement_gate' -Arguments $MovementArgs.ToArray()),
  (New-GateDefinition -Id 'quick_release_cable_snag' -ScriptName 'fr017-quick-release-cable-snag-gate.ps1' -ReadyStatus 'ready_for_engineering_review_or_final_physical_gate_audit' -NextRequiredInput 'scripts/fr017-new-release-cable-record.ps1 + FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json' -NextCommand 'create_non_powered_quick_release_cable_snag_record_then_rerun_release_cable_gate' -Arguments $ReleaseCableArgs.ToArray()),
  (New-GateDefinition -Id 'engineering_review' -ScriptName 'fr017-engineering-review-gate.ps1' -ReadyStatus 'ready_for_final_stage17_physical_gate_audit' -NextRequiredInput 'scripts/fr017-new-engineering-review-record.ps1 + FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json' -NextCommand 'create_professional_engineering_review_record_then_rerun_engineering_review_gate' -Arguments $EngineeringArgs.ToArray()),
  (New-GateDefinition -Id 'final_physical_gate' -ScriptName 'fr017-final-physical-gate.ps1' -ReadyStatus 'ready_for_stage17_final_physical_completion_decision' -NextRequiredInput 'scripts/fr017-new-final-decision-record.ps1 + FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json' -NextCommand 'create_human_final_decision_record_then_rerun_final_decision_record_gate' -Arguments $FinalArgs.ToArray()),
  (New-GateDefinition -Id 'final_decision_record' -ScriptName 'fr017-final-decision-record-gate.ps1' -ReadyStatus 'ready_for_completion_ledger_review' -NextRequiredInput 'scripts/fr017-new-final-decision-record.ps1 + FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json' -NextCommand 'create_human_final_decision_record_then_rerun_final_decision_record_gate' -Arguments $FinalDecisionArgs.ToArray()),
  (New-GateDefinition -Id 'completion_ledger' -ScriptName 'fr017-completion-ledger-gate.ps1' -ReadyStatus 'ready_for_operator_completion_ledger_update' -NextRequiredInput 'scripts/fr017-new-completion-ledger-handoff.ps1 + FR-017-COMPLETION-LEDGER-HANDOFF-TEMPLATE.md' -NextCommand 'create_candidate_completion_ledger_handoff_then_rerun_completion_ledger_gate' -Arguments $CompletionLedgerArgs.ToArray()),
  (New-GateDefinition -Id 'completion_ledger_update' -ScriptName 'fr017-completion-ledger-update-gate.ps1' -ReadyStatus 'ready_for_operator_stage17_completion_ledger_update_review' -NextRequiredInput 'docs/operations/COMPLETION_LEDGER.md or proposed completion ledger file containing reviewed FR-017 candidate handoff' -NextCommand 'update_or_provide_completion_ledger_file_then_rerun_completion_ledger_update_gate' -Arguments $CompletionLedgerUpdateArgs.ToArray())
)

$GateResults = New-Object System.Collections.Generic.List[object]
$FirstBlockingGate = $null
$FirstBlockingStatus = ''
$NextRequiredInput = ''
$NextCommand = ''
$FirstBlockingPreflightToolPath = ''
$FirstBlockingPreflightCommandTemplate = ''
$FirstBlockingPreflightContract = ''
$FirstBlockingPreflightStatus = ''
$FirstBlockingPreflightExitCode = 0
$FirstBlockingPreflightParseOk = $false
$FirstBlockingPreflightReadOnlyContract = $false
$FirstBlockingPreflightTemplateExists = $false
$FirstBlockingPreflightTemplateParseOk = $false
$FirstBlockingPreflightCandidateOutputPathReady = $false
$FirstBlockingPreflightOutputPath = ''
$FirstBlockingPreflightOutputExists = $false
$FirstBlockingPreflightOutputParentExists = $false
$FirstBlockingPreflightWroteFile = $false
$FirstBlockingPreflightPhysicalValidationComplete = $false
$FirstBlockingPreflightStage17CompletionClaimAllowed = $false
$FirstBlockingPreflightFr018ImplementationCleared = $false
$FirstBlockingUpdateToolPath = ''
$FirstBlockingUpdateCommandTemplate = ''
$FirstBlockingUpdateContract = ''
$FirstBlockingDetails = New-GateEvidenceDetails -Payload $null
$Status = 'ready_for_operator_stage17_completion_ledger_update_review'
$ExitCode = 0

foreach ($Gate in $Gates) {
  $Result = Invoke-JsonGate -ScriptName ([string]$Gate.script_name) -Arguments ([string[]]$Gate.arguments)
  $GateStatus = if ([bool]$Result.parse_ok) { [string]$Result.payload.status } else { 'failed_gate_parse' }
  $GateReady = [bool]$Result.parse_ok -and [int]$Result.exit_code -eq 0 -and $GateStatus -eq [string]$Gate.ready_status
  $GateFailed = (-not [bool]$Result.parse_ok) -or [int]$Result.exit_code -ne 0 -or $GateStatus.StartsWith('failed_') -or $GateStatus.StartsWith('missing_') -or $GateStatus.StartsWith('invalid_')
  $MeasurementSessionResult = $null
  if ([string]$Gate.id -eq 'measurement_intake' -and -not $GateReady) {
    $MeasurementSessionArgs = New-Object System.Collections.Generic.List[string]
    foreach ($Argument in ([string[]]$Gate.arguments)) {
      $MeasurementSessionArgs.Add($Argument) | Out-Null
    }
    Add-OptionalArg -Target $MeasurementSessionArgs -Name '-CandidateMeasurementPath' -Value $CandidateMeasurementPath
    $MeasurementSessionResult = Invoke-JsonGate -ScriptName 'fr017-measurement-session-brief.ps1' -Arguments $MeasurementSessionArgs.ToArray()
  }
  $GateDetails = if ($null -eq $MeasurementSessionResult) {
    New-GateEvidenceDetails -Payload $Result.payload
  } else {
    New-GateEvidenceDetails -Payload $Result.payload -MeasurementSessionPayload $MeasurementSessionResult.payload -MeasurementSessionParseOk ([bool]$MeasurementSessionResult.parse_ok) -MeasurementSessionExitCode ([int]$MeasurementSessionResult.exit_code)
  }

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
    $FirstBlockingPreflightToolPath = ''
    $FirstBlockingPreflightCommandTemplate = ''
    $FirstBlockingPreflightContract = ''
    $FirstBlockingPreflightStatus = ''
    $FirstBlockingPreflightExitCode = 0
    $FirstBlockingPreflightParseOk = $false
    $FirstBlockingPreflightReadOnlyContract = $false
    $FirstBlockingPreflightTemplateExists = $false
    $FirstBlockingPreflightTemplateParseOk = $false
    $FirstBlockingPreflightCandidateOutputPathReady = $false
    $FirstBlockingPreflightWroteFile = $false
    $FirstBlockingPreflightPhysicalValidationComplete = $false
    $FirstBlockingPreflightStage17CompletionClaimAllowed = $false
    $FirstBlockingPreflightFr018ImplementationCleared = $false
    if ([string]$Gate.id -eq 'measurement_intake') {
      $FirstBlockingPreflightToolPath = [string](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_preflight_tool_path')
      $FirstBlockingPreflightCommandTemplate = [string](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_preflight_command_template')
      $FirstBlockingPreflightContract = [string](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_preflight_contract')
      $FirstBlockingPreflightStatus = [string](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_preflight_status')
      $FirstBlockingPreflightExitCode = [int](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_preflight_exit_code' -Default 0)
      $FirstBlockingPreflightParseOk = [bool](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_preflight_parse_ok' -Default $false)
      $FirstBlockingPreflightReadOnlyContract = [bool](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_preflight_read_only_contract' -Default $false)
      $FirstBlockingPreflightTemplateExists = [bool](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_preflight_template_exists' -Default $false)
      $FirstBlockingPreflightTemplateParseOk = [bool](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_preflight_template_parse_ok' -Default $false)
      $FirstBlockingPreflightCandidateOutputPathReady = [bool](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_preflight_candidate_output_path_ready' -Default $false)
      $FirstBlockingPreflightOutputPath = [string](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_preflight_output_path')
      $FirstBlockingPreflightOutputExists = [bool](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_preflight_output_exists' -Default $false)
      $FirstBlockingPreflightOutputParentExists = [bool](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_preflight_output_parent_exists' -Default $false)
      $FirstBlockingPreflightWroteFile = [bool](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_preflight_wrote_file' -Default $false)
      $FirstBlockingPreflightPhysicalValidationComplete = [bool](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_preflight_physical_validation_complete' -Default $false)
      $FirstBlockingPreflightStage17CompletionClaimAllowed = [bool](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_preflight_stage17_completion_claim_allowed' -Default $false)
      $FirstBlockingPreflightFr018ImplementationCleared = [bool](Get-DetailsValue -Details $GateDetails -Name 'measurement_session_current_group_preflight_fr018_implementation_cleared' -Default $false)
    } elseif ([string]$Gate.id -eq 'mockup_readiness' -and -not $GateFailed) {
      $MockupInitializerArgs = New-Object System.Collections.Generic.List[string]
      $MockupInitializerArgs.Add('-Mode') | Out-Null
      $MockupInitializerArgs.Add('Status') | Out-Null
      Add-OptionalArg -Target $MockupInitializerArgs -Name '-MeasurementPath' -Value $MeasurementPath
      Add-OptionalArg -Target $MockupInitializerArgs -Name '-OutputPath' -Value $MockupPath
      $MockupInitializerPreflight = Invoke-JsonGate -ScriptName 'fr017-new-mockup-record.ps1' -Arguments $MockupInitializerArgs.ToArray()
      $FirstBlockingPreflightToolPath = Join-Path $RepoRoot 'scripts\fr017-new-mockup-record.ps1'
      $FirstBlockingPreflightCommandTemplate = if ([string]::IsNullOrWhiteSpace($MockupPath)) { '.\scripts\fr017-new-mockup-record.ps1 -Mode Status -MeasurementPath "{0}"' -f $MeasurementPath } else { '.\scripts\fr017-new-mockup-record.ps1 -Mode Status -MeasurementPath "{0}" -OutputPath "{1}"' -f $MeasurementPath, $MockupPath }
      $FirstBlockingPreflightContract = 'Read-only mockup initializer preflight for the non-powered FR-017 mockup record. It checks the mockup template, candidate output path when provided, and upstream measurement-intake readiness, writes no evidence, records no mockup build, and does not clear physical validation or FR-018.'
      $FirstBlockingPreflightStatus = if ([bool]$MockupInitializerPreflight.parse_ok) { [string](Get-PayloadValue -Payload $MockupInitializerPreflight.payload -Name 'status' -Default '') } else { 'failed_preflight_parse' }
      $FirstBlockingPreflightExitCode = [int]$MockupInitializerPreflight.exit_code
      $FirstBlockingPreflightParseOk = [bool]$MockupInitializerPreflight.parse_ok
      $FirstBlockingPreflightReadOnlyContract = [bool](Get-PayloadValue -Payload $MockupInitializerPreflight.payload -Name 'read_only_contract' -Default $false)
      $FirstBlockingPreflightTemplateExists = [bool](Get-PayloadValue -Payload $MockupInitializerPreflight.payload -Name 'template_exists' -Default $false)
      $FirstBlockingPreflightTemplateParseOk = [bool](Get-PayloadValue -Payload $MockupInitializerPreflight.payload -Name 'template_parse_ok' -Default $false)
      $FirstBlockingPreflightCandidateOutputPathReady = [bool](Get-PayloadValue -Payload $MockupInitializerPreflight.payload -Name 'candidate_output_path_ready' -Default $false)
      $FirstBlockingPreflightOutputPath = [string](Get-PayloadValue -Payload $MockupInitializerPreflight.payload -Name 'output_path' -Default '')
      $FirstBlockingPreflightOutputExists = [bool](Get-PayloadValue -Payload $MockupInitializerPreflight.payload -Name 'output_exists' -Default $false)
      $FirstBlockingPreflightOutputParentExists = [bool](Get-PayloadValue -Payload $MockupInitializerPreflight.payload -Name 'output_parent_exists' -Default $false)
      $FirstBlockingPreflightWroteFile = [bool](Get-PayloadValue -Payload $MockupInitializerPreflight.payload -Name 'wrote_file' -Default $false)
      $FirstBlockingPreflightPhysicalValidationComplete = [bool](Get-PayloadValue -Payload $MockupInitializerPreflight.payload -Name 'physical_validation_complete' -Default $false)
      $FirstBlockingPreflightFr018ImplementationCleared = [bool](Get-PayloadValue -Payload $MockupInitializerPreflight.payload -Name 'fr018_implementation_cleared' -Default $false)
    } elseif ([string]$Gate.id -eq 'mannequin_interface' -and -not $GateFailed) {
      $MannequinInitializerArgs = New-Object System.Collections.Generic.List[string]
      $MannequinInitializerArgs.Add('-Mode') | Out-Null
      $MannequinInitializerArgs.Add('Status') | Out-Null
      Add-OptionalArg -Target $MannequinInitializerArgs -Name '-MeasurementPath' -Value $MeasurementPath
      Add-OptionalArg -Target $MannequinInitializerArgs -Name '-MockupPath' -Value $MockupPath
      Add-OptionalArg -Target $MannequinInitializerArgs -Name '-OutputPath' -Value $MannequinPath
      $MannequinInitializerPreflight = Invoke-JsonGate -ScriptName 'fr017-new-mannequin-interface-record.ps1' -Arguments $MannequinInitializerArgs.ToArray()
      $FirstBlockingPreflightToolPath = Join-Path $RepoRoot 'scripts\fr017-new-mannequin-interface-record.ps1'
      $FirstBlockingPreflightCommandTemplate = if ([string]::IsNullOrWhiteSpace($MannequinPath)) { '.\scripts\fr017-new-mannequin-interface-record.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}"' -f $MeasurementPath, $MockupPath } else { '.\scripts\fr017-new-mannequin-interface-record.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -OutputPath "{2}"' -f $MeasurementPath, $MockupPath, $MannequinPath }
      $FirstBlockingPreflightContract = 'Read-only mannequin-interface initializer preflight for the non-powered FR-017 mannequin or arm-form interface record. It checks the mannequin template, candidate output path when provided, and upstream mockup readiness, writes no evidence, records no mannequin test, and does not clear physical validation, pilot testing, powered testing, or FR-018.'
      $FirstBlockingPreflightStatus = if ([bool]$MannequinInitializerPreflight.parse_ok) { [string](Get-PayloadValue -Payload $MannequinInitializerPreflight.payload -Name 'status' -Default '') } else { 'failed_preflight_parse' }
      $FirstBlockingPreflightExitCode = [int]$MannequinInitializerPreflight.exit_code
      $FirstBlockingPreflightParseOk = [bool]$MannequinInitializerPreflight.parse_ok
      $FirstBlockingPreflightReadOnlyContract = [bool](Get-PayloadValue -Payload $MannequinInitializerPreflight.payload -Name 'read_only_contract' -Default $false)
      $FirstBlockingPreflightTemplateExists = [bool](Get-PayloadValue -Payload $MannequinInitializerPreflight.payload -Name 'template_exists' -Default $false)
      $FirstBlockingPreflightTemplateParseOk = [bool](Get-PayloadValue -Payload $MannequinInitializerPreflight.payload -Name 'template_parse_ok' -Default $false)
      $FirstBlockingPreflightCandidateOutputPathReady = [bool](Get-PayloadValue -Payload $MannequinInitializerPreflight.payload -Name 'candidate_output_path_ready' -Default $false)
      $FirstBlockingPreflightOutputPath = [string](Get-PayloadValue -Payload $MannequinInitializerPreflight.payload -Name 'output_path' -Default '')
      $FirstBlockingPreflightOutputExists = [bool](Get-PayloadValue -Payload $MannequinInitializerPreflight.payload -Name 'output_exists' -Default $false)
      $FirstBlockingPreflightOutputParentExists = [bool](Get-PayloadValue -Payload $MannequinInitializerPreflight.payload -Name 'output_parent_exists' -Default $false)
      $FirstBlockingPreflightWroteFile = [bool](Get-PayloadValue -Payload $MannequinInitializerPreflight.payload -Name 'wrote_file' -Default $false)
      $FirstBlockingPreflightPhysicalValidationComplete = [bool](Get-PayloadValue -Payload $MannequinInitializerPreflight.payload -Name 'physical_validation_complete' -Default $false)
      $FirstBlockingPreflightFr018ImplementationCleared = [bool](Get-PayloadValue -Payload $MannequinInitializerPreflight.payload -Name 'fr018_implementation_cleared' -Default $false)
    } elseif ([string]$Gate.id -eq 'pilot_static_fit' -and -not $GateFailed) {
      $StaticFitInitializerArgs = New-Object System.Collections.Generic.List[string]
      $StaticFitInitializerArgs.Add('-Mode') | Out-Null
      $StaticFitInitializerArgs.Add('Status') | Out-Null
      Add-OptionalArg -Target $StaticFitInitializerArgs -Name '-MeasurementPath' -Value $MeasurementPath
      Add-OptionalArg -Target $StaticFitInitializerArgs -Name '-MockupPath' -Value $MockupPath
      Add-OptionalArg -Target $StaticFitInitializerArgs -Name '-MannequinPath' -Value $MannequinPath
      Add-OptionalArg -Target $StaticFitInitializerArgs -Name '-OutputPath' -Value $StaticFitPath
      $StaticFitInitializerPreflight = Invoke-JsonGate -ScriptName 'fr017-new-pilot-static-fit-record.ps1' -Arguments $StaticFitInitializerArgs.ToArray()
      $FirstBlockingPreflightToolPath = Join-Path $RepoRoot 'scripts\fr017-new-pilot-static-fit-record.ps1'
      $FirstBlockingPreflightCommandTemplate = if ([string]::IsNullOrWhiteSpace($StaticFitPath)) { '.\scripts\fr017-new-pilot-static-fit-record.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}"' -f $MeasurementPath, $MockupPath, $MannequinPath } else { '.\scripts\fr017-new-pilot-static-fit-record.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -OutputPath "{3}"' -f $MeasurementPath, $MockupPath, $MannequinPath, $StaticFitPath }
      $FirstBlockingPreflightContract = 'Read-only pilot static-fit initializer preflight for the non-powered FR-017 pilot static-fit record. It checks the static-fit template, candidate output path when provided, upstream mannequin-interface readiness, writes no evidence, records no pilot-contact test, and does not certify fit, clear pilot movement testing, physical validation, powered testing, or FR-018.'
      $FirstBlockingPreflightStatus = if ([bool]$StaticFitInitializerPreflight.parse_ok) { [string](Get-PayloadValue -Payload $StaticFitInitializerPreflight.payload -Name 'status' -Default '') } else { 'failed_preflight_parse' }
      $FirstBlockingPreflightExitCode = [int]$StaticFitInitializerPreflight.exit_code
      $FirstBlockingPreflightParseOk = [bool]$StaticFitInitializerPreflight.parse_ok
      $FirstBlockingPreflightReadOnlyContract = [bool](Get-PayloadValue -Payload $StaticFitInitializerPreflight.payload -Name 'read_only_contract' -Default $false)
      $FirstBlockingPreflightTemplateExists = [bool](Get-PayloadValue -Payload $StaticFitInitializerPreflight.payload -Name 'template_exists' -Default $false)
      $FirstBlockingPreflightTemplateParseOk = [bool](Get-PayloadValue -Payload $StaticFitInitializerPreflight.payload -Name 'template_parse_ok' -Default $false)
      $FirstBlockingPreflightCandidateOutputPathReady = [bool](Get-PayloadValue -Payload $StaticFitInitializerPreflight.payload -Name 'candidate_output_path_ready' -Default $false)
      $FirstBlockingPreflightOutputPath = [string](Get-PayloadValue -Payload $StaticFitInitializerPreflight.payload -Name 'output_path' -Default '')
      $FirstBlockingPreflightOutputExists = [bool](Get-PayloadValue -Payload $StaticFitInitializerPreflight.payload -Name 'output_exists' -Default $false)
      $FirstBlockingPreflightOutputParentExists = [bool](Get-PayloadValue -Payload $StaticFitInitializerPreflight.payload -Name 'output_parent_exists' -Default $false)
      $FirstBlockingPreflightWroteFile = [bool](Get-PayloadValue -Payload $StaticFitInitializerPreflight.payload -Name 'wrote_file' -Default $false)
      $FirstBlockingPreflightPhysicalValidationComplete = [bool](Get-PayloadValue -Payload $StaticFitInitializerPreflight.payload -Name 'physical_validation_complete' -Default $false)
      $FirstBlockingPreflightFr018ImplementationCleared = [bool](Get-PayloadValue -Payload $StaticFitInitializerPreflight.payload -Name 'fr018_implementation_cleared' -Default $false)
    } elseif ([string]$Gate.id -eq 'pilot_movement' -and -not $GateFailed) {
      $MovementInitializerArgs = New-Object System.Collections.Generic.List[string]
      $MovementInitializerArgs.Add('-Mode') | Out-Null
      $MovementInitializerArgs.Add('Status') | Out-Null
      Add-OptionalArg -Target $MovementInitializerArgs -Name '-MeasurementPath' -Value $MeasurementPath
      Add-OptionalArg -Target $MovementInitializerArgs -Name '-MockupPath' -Value $MockupPath
      Add-OptionalArg -Target $MovementInitializerArgs -Name '-MannequinPath' -Value $MannequinPath
      Add-OptionalArg -Target $MovementInitializerArgs -Name '-StaticFitPath' -Value $StaticFitPath
      Add-OptionalArg -Target $MovementInitializerArgs -Name '-OutputPath' -Value $MovementPath
      $MovementInitializerPreflight = Invoke-JsonGate -ScriptName 'fr017-new-pilot-movement-record.ps1' -Arguments $MovementInitializerArgs.ToArray()
      $FirstBlockingPreflightToolPath = Join-Path $RepoRoot 'scripts\fr017-new-pilot-movement-record.ps1'
      $FirstBlockingPreflightCommandTemplate = if ([string]::IsNullOrWhiteSpace($MovementPath)) { '.\scripts\fr017-new-pilot-movement-record.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -StaticFitPath "{3}"' -f $MeasurementPath, $MockupPath, $MannequinPath, $StaticFitPath } else { '.\scripts\fr017-new-pilot-movement-record.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -StaticFitPath "{3}" -OutputPath "{4}"' -f $MeasurementPath, $MockupPath, $MannequinPath, $StaticFitPath, $MovementPath }
      $FirstBlockingPreflightContract = 'Read-only pilot movement initializer preflight for the non-powered FR-017 pilot movement record. It checks the movement template, candidate output path when provided, upstream pilot static-fit readiness, writes no evidence, records no pilot movement test, and does not certify fit, clear release/cable testing, physical validation, powered testing, or FR-018.'
      $FirstBlockingPreflightStatus = if ([bool]$MovementInitializerPreflight.parse_ok) { [string](Get-PayloadValue -Payload $MovementInitializerPreflight.payload -Name 'status' -Default '') } else { 'failed_preflight_parse' }
      $FirstBlockingPreflightExitCode = [int]$MovementInitializerPreflight.exit_code
      $FirstBlockingPreflightParseOk = [bool]$MovementInitializerPreflight.parse_ok
      $FirstBlockingPreflightReadOnlyContract = [bool](Get-PayloadValue -Payload $MovementInitializerPreflight.payload -Name 'read_only_contract' -Default $false)
      $FirstBlockingPreflightTemplateExists = [bool](Get-PayloadValue -Payload $MovementInitializerPreflight.payload -Name 'template_exists' -Default $false)
      $FirstBlockingPreflightTemplateParseOk = [bool](Get-PayloadValue -Payload $MovementInitializerPreflight.payload -Name 'template_parse_ok' -Default $false)
      $FirstBlockingPreflightCandidateOutputPathReady = [bool](Get-PayloadValue -Payload $MovementInitializerPreflight.payload -Name 'candidate_output_path_ready' -Default $false)
      $FirstBlockingPreflightOutputPath = [string](Get-PayloadValue -Payload $MovementInitializerPreflight.payload -Name 'output_path' -Default '')
      $FirstBlockingPreflightOutputExists = [bool](Get-PayloadValue -Payload $MovementInitializerPreflight.payload -Name 'output_exists' -Default $false)
      $FirstBlockingPreflightOutputParentExists = [bool](Get-PayloadValue -Payload $MovementInitializerPreflight.payload -Name 'output_parent_exists' -Default $false)
      $FirstBlockingPreflightWroteFile = [bool](Get-PayloadValue -Payload $MovementInitializerPreflight.payload -Name 'wrote_file' -Default $false)
      $FirstBlockingPreflightPhysicalValidationComplete = [bool](Get-PayloadValue -Payload $MovementInitializerPreflight.payload -Name 'physical_validation_complete' -Default $false)
      $FirstBlockingPreflightFr018ImplementationCleared = [bool](Get-PayloadValue -Payload $MovementInitializerPreflight.payload -Name 'fr018_implementation_cleared' -Default $false)
    } elseif ([string]$Gate.id -eq 'quick_release_cable_snag' -and -not $GateFailed) {
      $ReleaseCableInitializerArgs = New-Object System.Collections.Generic.List[string]
      $ReleaseCableInitializerArgs.Add('-Mode') | Out-Null
      $ReleaseCableInitializerArgs.Add('Status') | Out-Null
      Add-OptionalArg -Target $ReleaseCableInitializerArgs -Name '-MeasurementPath' -Value $MeasurementPath
      Add-OptionalArg -Target $ReleaseCableInitializerArgs -Name '-MockupPath' -Value $MockupPath
      Add-OptionalArg -Target $ReleaseCableInitializerArgs -Name '-MannequinPath' -Value $MannequinPath
      Add-OptionalArg -Target $ReleaseCableInitializerArgs -Name '-StaticFitPath' -Value $StaticFitPath
      Add-OptionalArg -Target $ReleaseCableInitializerArgs -Name '-MovementPath' -Value $MovementPath
      Add-OptionalArg -Target $ReleaseCableInitializerArgs -Name '-OutputPath' -Value $ReleaseCablePath
      $ReleaseCableInitializerPreflight = Invoke-JsonGate -ScriptName 'fr017-new-release-cable-record.ps1' -Arguments $ReleaseCableInitializerArgs.ToArray()
      $FirstBlockingPreflightToolPath = Join-Path $RepoRoot 'scripts\fr017-new-release-cable-record.ps1'
      $FirstBlockingPreflightCommandTemplate = if ([string]::IsNullOrWhiteSpace($ReleaseCablePath)) { '.\scripts\fr017-new-release-cable-record.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -StaticFitPath "{3}" -MovementPath "{4}"' -f $MeasurementPath, $MockupPath, $MannequinPath, $StaticFitPath, $MovementPath } else { '.\scripts\fr017-new-release-cable-record.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -StaticFitPath "{3}" -MovementPath "{4}" -OutputPath "{5}"' -f $MeasurementPath, $MockupPath, $MannequinPath, $StaticFitPath, $MovementPath, $ReleaseCablePath }
      $FirstBlockingPreflightContract = 'Read-only quick-release/cable-snag initializer preflight for the non-powered FR-017 release/cable record. It checks the release/cable template, candidate output path when provided, upstream pilot movement readiness, writes no evidence, records no release or cable-snag test, and does not certify emergency release safety, clear engineering review, physical validation, powered testing, or FR-018.'
      $FirstBlockingPreflightStatus = if ([bool]$ReleaseCableInitializerPreflight.parse_ok) { [string](Get-PayloadValue -Payload $ReleaseCableInitializerPreflight.payload -Name 'status' -Default '') } else { 'failed_preflight_parse' }
      $FirstBlockingPreflightExitCode = [int]$ReleaseCableInitializerPreflight.exit_code
      $FirstBlockingPreflightParseOk = [bool]$ReleaseCableInitializerPreflight.parse_ok
      $FirstBlockingPreflightReadOnlyContract = [bool](Get-PayloadValue -Payload $ReleaseCableInitializerPreflight.payload -Name 'read_only_contract' -Default $false)
      $FirstBlockingPreflightTemplateExists = [bool](Get-PayloadValue -Payload $ReleaseCableInitializerPreflight.payload -Name 'template_exists' -Default $false)
      $FirstBlockingPreflightTemplateParseOk = [bool](Get-PayloadValue -Payload $ReleaseCableInitializerPreflight.payload -Name 'template_parse_ok' -Default $false)
      $FirstBlockingPreflightCandidateOutputPathReady = [bool](Get-PayloadValue -Payload $ReleaseCableInitializerPreflight.payload -Name 'candidate_output_path_ready' -Default $false)
      $FirstBlockingPreflightOutputPath = [string](Get-PayloadValue -Payload $ReleaseCableInitializerPreflight.payload -Name 'output_path' -Default '')
      $FirstBlockingPreflightOutputExists = [bool](Get-PayloadValue -Payload $ReleaseCableInitializerPreflight.payload -Name 'output_exists' -Default $false)
      $FirstBlockingPreflightOutputParentExists = [bool](Get-PayloadValue -Payload $ReleaseCableInitializerPreflight.payload -Name 'output_parent_exists' -Default $false)
      $FirstBlockingPreflightWroteFile = [bool](Get-PayloadValue -Payload $ReleaseCableInitializerPreflight.payload -Name 'wrote_file' -Default $false)
      $FirstBlockingPreflightPhysicalValidationComplete = [bool](Get-PayloadValue -Payload $ReleaseCableInitializerPreflight.payload -Name 'physical_validation_complete' -Default $false)
      $FirstBlockingPreflightFr018ImplementationCleared = [bool](Get-PayloadValue -Payload $ReleaseCableInitializerPreflight.payload -Name 'fr018_implementation_cleared' -Default $false)
    } elseif ([string]$Gate.id -eq 'engineering_review' -and -not $GateFailed) {
      $EngineeringReviewInitializerArgs = New-Object System.Collections.Generic.List[string]
      $EngineeringReviewInitializerArgs.Add('-Mode') | Out-Null
      $EngineeringReviewInitializerArgs.Add('Status') | Out-Null
      Add-OptionalArg -Target $EngineeringReviewInitializerArgs -Name '-MeasurementPath' -Value $MeasurementPath
      Add-OptionalArg -Target $EngineeringReviewInitializerArgs -Name '-MockupPath' -Value $MockupPath
      Add-OptionalArg -Target $EngineeringReviewInitializerArgs -Name '-MannequinPath' -Value $MannequinPath
      Add-OptionalArg -Target $EngineeringReviewInitializerArgs -Name '-StaticFitPath' -Value $StaticFitPath
      Add-OptionalArg -Target $EngineeringReviewInitializerArgs -Name '-MovementPath' -Value $MovementPath
      Add-OptionalArg -Target $EngineeringReviewInitializerArgs -Name '-ReleaseCablePath' -Value $ReleaseCablePath
      Add-OptionalArg -Target $EngineeringReviewInitializerArgs -Name '-OutputPath' -Value $EngineeringReviewPath
      $EngineeringReviewInitializerPreflight = Invoke-JsonGate -ScriptName 'fr017-new-engineering-review-record.ps1' -Arguments $EngineeringReviewInitializerArgs.ToArray()
      $FirstBlockingPreflightToolPath = Join-Path $RepoRoot 'scripts\fr017-new-engineering-review-record.ps1'
      $FirstBlockingPreflightCommandTemplate = if ([string]::IsNullOrWhiteSpace($EngineeringReviewPath)) { '.\scripts\fr017-new-engineering-review-record.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -StaticFitPath "{3}" -MovementPath "{4}" -ReleaseCablePath "{5}"' -f $MeasurementPath, $MockupPath, $MannequinPath, $StaticFitPath, $MovementPath, $ReleaseCablePath } else { '.\scripts\fr017-new-engineering-review-record.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -StaticFitPath "{3}" -MovementPath "{4}" -ReleaseCablePath "{5}" -OutputPath "{6}"' -f $MeasurementPath, $MockupPath, $MannequinPath, $StaticFitPath, $MovementPath, $ReleaseCablePath, $EngineeringReviewPath }
      $FirstBlockingPreflightContract = 'Read-only professional engineering-review initializer preflight for the non-powered FR-017 engineering review record. It checks the engineering-review template, candidate output path when provided, upstream quick-release/cable-snag readiness, writes no evidence, records no professional review, and does not certify pilot safety, complete the final physical gate, approve load-bearing use, clear powered or frame-coupled testing, or clear FR-018.'
      $FirstBlockingPreflightStatus = if ([bool]$EngineeringReviewInitializerPreflight.parse_ok) { [string](Get-PayloadValue -Payload $EngineeringReviewInitializerPreflight.payload -Name 'status' -Default '') } else { 'failed_preflight_parse' }
      $FirstBlockingPreflightExitCode = [int]$EngineeringReviewInitializerPreflight.exit_code
      $FirstBlockingPreflightParseOk = [bool]$EngineeringReviewInitializerPreflight.parse_ok
      $FirstBlockingPreflightReadOnlyContract = [bool](Get-PayloadValue -Payload $EngineeringReviewInitializerPreflight.payload -Name 'read_only_contract' -Default $false)
      $FirstBlockingPreflightTemplateExists = [bool](Get-PayloadValue -Payload $EngineeringReviewInitializerPreflight.payload -Name 'template_exists' -Default $false)
      $FirstBlockingPreflightTemplateParseOk = [bool](Get-PayloadValue -Payload $EngineeringReviewInitializerPreflight.payload -Name 'template_parse_ok' -Default $false)
      $FirstBlockingPreflightCandidateOutputPathReady = [bool](Get-PayloadValue -Payload $EngineeringReviewInitializerPreflight.payload -Name 'candidate_output_path_ready' -Default $false)
      $FirstBlockingPreflightOutputPath = [string](Get-PayloadValue -Payload $EngineeringReviewInitializerPreflight.payload -Name 'output_path' -Default '')
      $FirstBlockingPreflightOutputExists = [bool](Get-PayloadValue -Payload $EngineeringReviewInitializerPreflight.payload -Name 'output_exists' -Default $false)
      $FirstBlockingPreflightOutputParentExists = [bool](Get-PayloadValue -Payload $EngineeringReviewInitializerPreflight.payload -Name 'output_parent_exists' -Default $false)
      $FirstBlockingPreflightWroteFile = [bool](Get-PayloadValue -Payload $EngineeringReviewInitializerPreflight.payload -Name 'wrote_file' -Default $false)
      $FirstBlockingPreflightPhysicalValidationComplete = [bool](Get-PayloadValue -Payload $EngineeringReviewInitializerPreflight.payload -Name 'physical_validation_complete' -Default $false)
      $FirstBlockingPreflightFr018ImplementationCleared = [bool](Get-PayloadValue -Payload $EngineeringReviewInitializerPreflight.payload -Name 'fr018_implementation_cleared' -Default $false)
    } elseif ([string]$Gate.id -eq 'final_decision_record' -and -not $GateFailed) {
      $FinalDecisionInitializerArgs = New-Object System.Collections.Generic.List[string]
      $FinalDecisionInitializerArgs.Add('-Mode') | Out-Null
      $FinalDecisionInitializerArgs.Add('Status') | Out-Null
      Add-OptionalArg -Target $FinalDecisionInitializerArgs -Name '-MeasurementPath' -Value $MeasurementPath
      Add-OptionalArg -Target $FinalDecisionInitializerArgs -Name '-MockupPath' -Value $MockupPath
      Add-OptionalArg -Target $FinalDecisionInitializerArgs -Name '-MannequinPath' -Value $MannequinPath
      Add-OptionalArg -Target $FinalDecisionInitializerArgs -Name '-StaticFitPath' -Value $StaticFitPath
      Add-OptionalArg -Target $FinalDecisionInitializerArgs -Name '-MovementPath' -Value $MovementPath
      Add-OptionalArg -Target $FinalDecisionInitializerArgs -Name '-ReleaseCablePath' -Value $ReleaseCablePath
      Add-OptionalArg -Target $FinalDecisionInitializerArgs -Name '-EngineeringReviewPath' -Value $EngineeringReviewPath
      Add-OptionalArg -Target $FinalDecisionInitializerArgs -Name '-OutputPath' -Value $FinalDecisionPath
      $FinalDecisionInitializerPreflight = Invoke-JsonGate -ScriptName 'fr017-new-final-decision-record.ps1' -Arguments $FinalDecisionInitializerArgs.ToArray()
      $FirstBlockingPreflightToolPath = Join-Path $RepoRoot 'scripts\fr017-new-final-decision-record.ps1'
      $FirstBlockingPreflightCommandTemplate = if ([string]::IsNullOrWhiteSpace($FinalDecisionPath)) { '.\scripts\fr017-new-final-decision-record.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -StaticFitPath "{3}" -MovementPath "{4}" -ReleaseCablePath "{5}" -EngineeringReviewPath "{6}"' -f $MeasurementPath, $MockupPath, $MannequinPath, $StaticFitPath, $MovementPath, $ReleaseCablePath, $EngineeringReviewPath } else { '.\scripts\fr017-new-final-decision-record.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -StaticFitPath "{3}" -MovementPath "{4}" -ReleaseCablePath "{5}" -EngineeringReviewPath "{6}" -OutputPath "{7}"' -f $MeasurementPath, $MockupPath, $MannequinPath, $StaticFitPath, $MovementPath, $ReleaseCablePath, $EngineeringReviewPath, $FinalDecisionPath }
      $FirstBlockingPreflightContract = 'Read-only human final-decision initializer preflight for the FR-017 final decision record. It checks the final decision template, candidate output path when provided, upstream final physical gate decision readiness, writes no final decision record, saves no final physical gate record, writes no completion ledger, and does not mark physical validation complete, approve load-bearing use, clear powered or frame-coupled testing, or clear FR-018.'
      $FirstBlockingPreflightStatus = if ([bool]$FinalDecisionInitializerPreflight.parse_ok) { [string](Get-PayloadValue -Payload $FinalDecisionInitializerPreflight.payload -Name 'status' -Default '') } else { 'failed_preflight_parse' }
      $FirstBlockingPreflightExitCode = [int]$FinalDecisionInitializerPreflight.exit_code
      $FirstBlockingPreflightParseOk = [bool]$FinalDecisionInitializerPreflight.parse_ok
      $FirstBlockingPreflightReadOnlyContract = [bool](Get-PayloadValue -Payload $FinalDecisionInitializerPreflight.payload -Name 'read_only_contract' -Default $false)
      $FirstBlockingPreflightTemplateExists = [bool](Get-PayloadValue -Payload $FinalDecisionInitializerPreflight.payload -Name 'template_exists' -Default $false)
      $FirstBlockingPreflightTemplateParseOk = [bool](Get-PayloadValue -Payload $FinalDecisionInitializerPreflight.payload -Name 'template_parse_ok' -Default $false)
      $FirstBlockingPreflightCandidateOutputPathReady = [bool](Get-PayloadValue -Payload $FinalDecisionInitializerPreflight.payload -Name 'candidate_output_path_ready' -Default $false)
      $FirstBlockingPreflightOutputPath = [string](Get-PayloadValue -Payload $FinalDecisionInitializerPreflight.payload -Name 'output_path' -Default '')
      $FirstBlockingPreflightOutputExists = [bool](Get-PayloadValue -Payload $FinalDecisionInitializerPreflight.payload -Name 'output_exists' -Default $false)
      $FirstBlockingPreflightOutputParentExists = [bool](Get-PayloadValue -Payload $FinalDecisionInitializerPreflight.payload -Name 'output_parent_exists' -Default $false)
      $FirstBlockingPreflightWroteFile = [bool](Get-PayloadValue -Payload $FinalDecisionInitializerPreflight.payload -Name 'wrote_file' -Default $false)
      $FirstBlockingPreflightPhysicalValidationComplete = [bool](Get-PayloadValue -Payload $FinalDecisionInitializerPreflight.payload -Name 'physical_validation_complete' -Default $false)
      $FirstBlockingPreflightFr018ImplementationCleared = [bool](Get-PayloadValue -Payload $FinalDecisionInitializerPreflight.payload -Name 'fr018_implementation_cleared' -Default $false)
    } elseif ([string]$Gate.id -eq 'completion_ledger' -and -not $GateFailed) {
      $CompletionLedgerInitializerArgs = New-Object System.Collections.Generic.List[string]
      $CompletionLedgerInitializerArgs.Add('-Mode') | Out-Null
      $CompletionLedgerInitializerArgs.Add('Status') | Out-Null
      Add-OptionalArg -Target $CompletionLedgerInitializerArgs -Name '-MeasurementPath' -Value $MeasurementPath
      Add-OptionalArg -Target $CompletionLedgerInitializerArgs -Name '-MockupPath' -Value $MockupPath
      Add-OptionalArg -Target $CompletionLedgerInitializerArgs -Name '-MannequinPath' -Value $MannequinPath
      Add-OptionalArg -Target $CompletionLedgerInitializerArgs -Name '-StaticFitPath' -Value $StaticFitPath
      Add-OptionalArg -Target $CompletionLedgerInitializerArgs -Name '-MovementPath' -Value $MovementPath
      Add-OptionalArg -Target $CompletionLedgerInitializerArgs -Name '-ReleaseCablePath' -Value $ReleaseCablePath
      Add-OptionalArg -Target $CompletionLedgerInitializerArgs -Name '-EngineeringReviewPath' -Value $EngineeringReviewPath
      Add-OptionalArg -Target $CompletionLedgerInitializerArgs -Name '-FinalDecisionPath' -Value $FinalDecisionPath
      Add-OptionalArg -Target $CompletionLedgerInitializerArgs -Name '-OutputPath' -Value $LedgerEntryPath
      $CompletionLedgerInitializerPreflight = Invoke-JsonGate -ScriptName 'fr017-new-completion-ledger-handoff.ps1' -Arguments $CompletionLedgerInitializerArgs.ToArray()
      $FirstBlockingPreflightToolPath = Join-Path $RepoRoot 'scripts\fr017-new-completion-ledger-handoff.ps1'
      $FirstBlockingPreflightCommandTemplate = if ([string]::IsNullOrWhiteSpace($LedgerEntryPath)) { '.\scripts\fr017-new-completion-ledger-handoff.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -StaticFitPath "{3}" -MovementPath "{4}" -ReleaseCablePath "{5}" -EngineeringReviewPath "{6}" -FinalDecisionPath "{7}"' -f $MeasurementPath, $MockupPath, $MannequinPath, $StaticFitPath, $MovementPath, $ReleaseCablePath, $EngineeringReviewPath, $FinalDecisionPath } else { '.\scripts\fr017-new-completion-ledger-handoff.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -StaticFitPath "{3}" -MovementPath "{4}" -ReleaseCablePath "{5}" -EngineeringReviewPath "{6}" -FinalDecisionPath "{7}" -OutputPath "{8}"' -f $MeasurementPath, $MockupPath, $MannequinPath, $StaticFitPath, $MovementPath, $ReleaseCablePath, $EngineeringReviewPath, $FinalDecisionPath, $LedgerEntryPath }
      $FirstBlockingPreflightContract = 'Read-only completion-ledger handoff initializer preflight for the FR-017 candidate ledger handoff. It checks the handoff template, candidate output path when provided, and upstream final-decision readiness, writes no candidate handoff, writes no completion ledger, and does not mark physical validation complete, permit a Stage 17 completion claim, approve load-bearing use, clear powered or frame-coupled testing, or clear FR-018.'
      $FirstBlockingPreflightStatus = if ([bool]$CompletionLedgerInitializerPreflight.parse_ok) { [string](Get-PayloadValue -Payload $CompletionLedgerInitializerPreflight.payload -Name 'status' -Default '') } else { 'failed_preflight_parse' }
      $FirstBlockingPreflightExitCode = [int]$CompletionLedgerInitializerPreflight.exit_code
      $FirstBlockingPreflightParseOk = [bool]$CompletionLedgerInitializerPreflight.parse_ok
      $FirstBlockingPreflightReadOnlyContract = [bool](Get-PayloadValue -Payload $CompletionLedgerInitializerPreflight.payload -Name 'read_only_contract' -Default $false)
      $FirstBlockingPreflightTemplateExists = [bool](Get-PayloadValue -Payload $CompletionLedgerInitializerPreflight.payload -Name 'template_exists' -Default $false)
      $FirstBlockingPreflightTemplateParseOk = [bool](Get-PayloadValue -Payload $CompletionLedgerInitializerPreflight.payload -Name 'template_parse_ok' -Default $false)
      $FirstBlockingPreflightCandidateOutputPathReady = [bool](Get-PayloadValue -Payload $CompletionLedgerInitializerPreflight.payload -Name 'candidate_output_path_ready' -Default $false)
      $FirstBlockingPreflightOutputPath = [string](Get-PayloadValue -Payload $CompletionLedgerInitializerPreflight.payload -Name 'output_path' -Default '')
      $FirstBlockingPreflightOutputExists = [bool](Get-PayloadValue -Payload $CompletionLedgerInitializerPreflight.payload -Name 'output_exists' -Default $false)
      $FirstBlockingPreflightOutputParentExists = [bool](Get-PayloadValue -Payload $CompletionLedgerInitializerPreflight.payload -Name 'output_parent_exists' -Default $false)
      $FirstBlockingPreflightWroteFile = [bool](Get-PayloadValue -Payload $CompletionLedgerInitializerPreflight.payload -Name 'wrote_file' -Default $false)
      $FirstBlockingPreflightPhysicalValidationComplete = [bool](Get-PayloadValue -Payload $CompletionLedgerInitializerPreflight.payload -Name 'physical_validation_complete' -Default $false)
      $FirstBlockingPreflightFr018ImplementationCleared = [bool](Get-PayloadValue -Payload $CompletionLedgerInitializerPreflight.payload -Name 'fr018_implementation_cleared' -Default $false)
    } elseif ([string]$Gate.id -eq 'completion_ledger_update' -and -not $GateFailed) {
      $CompletionLedgerPathForReadback = [string](Get-DetailsValue -Details $GateDetails -Name 'completion_ledger_path')
      $CompletionLedgerParent = if ([string]::IsNullOrWhiteSpace($CompletionLedgerPathForReadback)) { '' } else { Split-Path -Parent $CompletionLedgerPathForReadback }
      $FirstBlockingPreflightToolPath = Join-Path $RepoRoot 'scripts\fr017-completion-ledger-update-gate.ps1'
      $FirstBlockingPreflightCommandTemplate = '.\scripts\fr017-completion-ledger-update-gate.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -StaticFitPath "{3}" -MovementPath "{4}" -ReleaseCablePath "{5}" -EngineeringReviewPath "{6}" -FinalDecisionPath "{7}" -LedgerEntryPath "{8}" -CompletionLedgerPath "{9}"' -f $MeasurementPath, $MockupPath, $MannequinPath, $StaticFitPath, $MovementPath, $ReleaseCablePath, $EngineeringReviewPath, $FinalDecisionPath, $LedgerEntryPath, $CompletionLedgerPath
      $FirstBlockingPreflightContract = 'Read-only completion-ledger update review preflight for FR-017. It reuses the current completion-ledger-update gate result, checks that the actual or proposed completion ledger contains the reviewed candidate handoff section with blocked-clearance language, writes no completion ledger, writes no evidence, and does not mark physical validation complete, permit a Stage 17 completion claim, approve load-bearing use, clear powered or frame-coupled testing, or clear FR-018.'
      $FirstBlockingPreflightStatus = $GateStatus
      $FirstBlockingPreflightExitCode = [int]$Result.exit_code
      $FirstBlockingPreflightParseOk = [bool]$Result.parse_ok
      $FirstBlockingPreflightReadOnlyContract = [bool](Get-PayloadValue -Payload $Result.payload -Name 'read_only_contract' -Default $false)
      $FirstBlockingPreflightTemplateExists = $false
      $FirstBlockingPreflightTemplateParseOk = $false
      $FirstBlockingPreflightCandidateOutputPathReady = $false
      $FirstBlockingPreflightOutputPath = $CompletionLedgerPathForReadback
      $FirstBlockingPreflightOutputExists = [bool](Get-DetailsValue -Details $GateDetails -Name 'completion_ledger_exists' -Default $false)
      $FirstBlockingPreflightOutputParentExists = -not [string]::IsNullOrWhiteSpace($CompletionLedgerParent) -and (Test-Path -LiteralPath $CompletionLedgerParent -PathType Container)
      $FirstBlockingPreflightWroteFile = [bool](Get-PayloadValue -Payload $Result.payload -Name 'writes_data' -Default $false)
      $FirstBlockingPreflightPhysicalValidationComplete = [bool](Get-PayloadValue -Payload $Result.payload -Name 'physical_validation_complete' -Default $false)
      $FirstBlockingPreflightFr018ImplementationCleared = [bool](Get-PayloadValue -Payload $Result.payload -Name 'fr018_implementation_cleared' -Default $false)
    }
    $FirstBlockingUpdateHint = New-FirstBlockingUpdateHint -GateId ([string]$Gate.id) -GateFailed $GateFailed -GateDetails $GateDetails
    $FirstBlockingUpdateToolPath = [string]$FirstBlockingUpdateHint.tool_path
    $FirstBlockingUpdateCommandTemplate = [string]$FirstBlockingUpdateHint.command_template
    $FirstBlockingUpdateContract = [string]$FirstBlockingUpdateHint.contract
    if ($GateFailed) {
      $Status = 'failed_{0}' -f [string]$Gate.id
      $ExitCode = 1
    } else {
      $Status = 'blocked_on_{0}' -f [string]$Gate.id
    }
    break
  }
}

$CompletionLedgerHandoffReady = $false
foreach ($GateResult in $GateResults) {
  if ([string]$GateResult.id -eq 'completion_ledger' -and [bool]$GateResult.ready_for_next_gate) {
    $CompletionLedgerHandoffReady = $true
    break
  }
}
$CompletionLedgerUpdateReviewReady = $Status -eq 'ready_for_operator_stage17_completion_ledger_update_review'
$EvidenceChainDecisionReady = $CompletionLedgerUpdateReviewReady

$Output = [ordered]@{
  kind = 'francis.fr017.evidence_chain_status'
  mode = $Mode
  status = $Status
  evidence_chain_decision_ready = $EvidenceChainDecisionReady
  ledger_completion_review_ready = $CompletionLedgerUpdateReviewReady
  completion_ledger_handoff_ready = $CompletionLedgerHandoffReady
  completion_ledger_update_review_ready = $CompletionLedgerUpdateReviewReady
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
  first_blocking_preflight_tool_path = $FirstBlockingPreflightToolPath
  first_blocking_preflight_command_template = $FirstBlockingPreflightCommandTemplate
  first_blocking_preflight_contract = $FirstBlockingPreflightContract
  first_blocking_preflight_status = $FirstBlockingPreflightStatus
  first_blocking_preflight_exit_code = $FirstBlockingPreflightExitCode
  first_blocking_preflight_parse_ok = $FirstBlockingPreflightParseOk
  first_blocking_preflight_read_only_contract = $FirstBlockingPreflightReadOnlyContract
  first_blocking_preflight_template_exists = $FirstBlockingPreflightTemplateExists
  first_blocking_preflight_template_parse_ok = $FirstBlockingPreflightTemplateParseOk
  first_blocking_preflight_candidate_output_path_ready = $FirstBlockingPreflightCandidateOutputPathReady
  first_blocking_preflight_output_path = $FirstBlockingPreflightOutputPath
  first_blocking_preflight_output_exists = $FirstBlockingPreflightOutputExists
  first_blocking_preflight_output_parent_exists = $FirstBlockingPreflightOutputParentExists
  first_blocking_preflight_wrote_file = $FirstBlockingPreflightWroteFile
  first_blocking_preflight_physical_validation_complete = $FirstBlockingPreflightPhysicalValidationComplete
  first_blocking_preflight_stage17_completion_claim_allowed = $FirstBlockingPreflightStage17CompletionClaimAllowed
  first_blocking_preflight_fr018_implementation_cleared = $FirstBlockingPreflightFr018ImplementationCleared
  first_blocking_update_tool_path = $FirstBlockingUpdateToolPath
  first_blocking_update_command_template = $FirstBlockingUpdateCommandTemplate
  first_blocking_update_contract = $FirstBlockingUpdateContract
  first_blocking_details = $FirstBlockingDetails
  gates_ran = $GateResults.Count
  gate_count = $Gates.Count
  gate_results = @($GateResults.ToArray())
  no_fake_validation_lock = 'This chain-status command reports evidence, completion-ledger handoff readiness, and read-only completion-ledger update review only. It never writes the ledger, marks physical_validation_complete, permits a Stage 17 completion claim, or clears FR-018.'
}

if ($Mode -eq 'Summary') {
  $Output = New-EvidenceChainSummary -StatusPayload $Output
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
