[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$MeasurementPath = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$MeasurementIntakeScript = Join-Path $PSScriptRoot 'fr017-measurement-intake.ps1'

function Resolve-BriefPath {
  param([string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path)) {
    return ''
  }
  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Path))
}

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
    [string]$ScriptPath,
    [string[]]$Arguments
  )

  $PowerShellExe = (Get-Process -Id $PID).Path
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
    raw_output = ($RawOutput | Out-String)
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

function Find-CaptureStatus {
  param(
    [object[]]$Statuses,
    [string]$GroupId
  )

  if ([string]::IsNullOrWhiteSpace($GroupId)) {
    return $null
  }
  foreach ($StatusItem in $Statuses) {
    $Property = $StatusItem.PSObject.Properties['id']
    if ($null -ne $Property -and [string]$Property.Value -eq $GroupId) {
      return $StatusItem
    }
  }
  return $null
}

$IntakeArgs = New-Object System.Collections.Generic.List[string]
$IntakeArgs.Add('-Mode') | Out-Null
$IntakeArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $IntakeArgs -Name '-MeasurementPath' -Value $MeasurementPath

$IntakeGate = Invoke-JsonGate -ScriptPath $MeasurementIntakeScript -Arguments $IntakeArgs.ToArray()
$IntakeStatus = if ([bool]$IntakeGate.parse_ok) { [string](Get-PayloadValue -Payload $IntakeGate.payload -Name 'status' -Default '') } else { 'failed_gate_parse' }
$IntakeFailed = (-not [bool]$IntakeGate.parse_ok) -or [int]$IntakeGate.exit_code -ne 0 -or $IntakeStatus.StartsWith('failed_') -or $IntakeStatus.StartsWith('invalid_') -or $IntakeStatus.StartsWith('missing_')
$IntakeReady = [bool]$IntakeGate.parse_ok -and [int]$IntakeGate.exit_code -eq 0 -and $IntakeStatus -eq 'ready_for_non_powered_mockup_patterning'

$CaptureStatuses = @(Get-PayloadObjectArrayProperty -Payload $IntakeGate.payload -Name 'measurement_capture_plan_status')
$FirstBlockingGroupId = [string](Get-PayloadValue -Payload $IntakeGate.payload -Name 'measurement_capture_first_blocking_group_id' -Default '')
$FirstBlockingGroup = Find-CaptureStatus -Statuses $CaptureStatuses -GroupId $FirstBlockingGroupId

$CurrentMissingFields = @()
$CurrentInvalidFields = @()
$CurrentBlockingSignals = @()
$CurrentRequiredAction = [string](Get-PayloadValue -Payload $IntakeGate.payload -Name 'measurement_capture_first_blocking_group_action' -Default '')
if ($null -ne $FirstBlockingGroup) {
  $CurrentMissingFields = @(Get-PayloadArrayProperty -Payload $FirstBlockingGroup -Name 'missing_fields')
  $CurrentInvalidFields = @(Get-PayloadArrayProperty -Payload $FirstBlockingGroup -Name 'invalid_fields')
  $CurrentBlockingSignals = @(Get-PayloadArrayProperty -Payload $FirstBlockingGroup -Name 'blocking_signals')
  $CurrentRequiredAction = [string](Get-PayloadValue -Payload $FirstBlockingGroup -Name 'required_action' -Default $CurrentRequiredAction)
}

if ($IntakeReady) {
  $Status = 'ready_for_non_powered_mockup_patterning_handoff'
  $ExitCode = 0
  $NextOperatorAction = 'rerun_mockup_readiness_gate_with_the_accepted_measurement_record_without_claiming_physical_validation'
} elseif ($IntakeFailed) {
  $Status = 'failed_measurement_session_brief'
  $ExitCode = 1
  $NextOperatorAction = 'stop_measurement_session_and_resolve_intake_failure_before_any_mockup_or_FR-018_work'
} else {
  $Status = 'measurement_session_input_required'
  $ExitCode = 0
  $NextOperatorAction = 'complete_first_blocking_measurement_capture_group_then_rerun_measurement_intake'
}

$Output = [ordered]@{
  kind = 'francis.fr017.measurement_session_brief'
  mode = $Mode
  status = $Status
  intake_status = $IntakeStatus
  intake_exit_code = [int]$IntakeGate.exit_code
  intake_parse_ok = [bool]$IntakeGate.parse_ok
  intake_failed = $IntakeFailed
  intake_ready_for_non_powered_mockup_patterning = $IntakeReady
  measurement_path = Resolve-BriefPath -Path $MeasurementPath
  using_template = if ($null -eq $IntakeGate.payload -or $null -eq $IntakeGate.payload.PSObject.Properties['using_template']) { [string]::IsNullOrWhiteSpace($MeasurementPath) } else { [bool]$IntakeGate.payload.using_template }
  first_blocking_group_id = $FirstBlockingGroupId
  first_blocking_group_status = [string](Get-PayloadValue -Payload $IntakeGate.payload -Name 'measurement_capture_first_blocking_group_status' -Default '')
  first_blocking_group_action = [string](Get-PayloadValue -Payload $IntakeGate.payload -Name 'measurement_capture_first_blocking_group_action' -Default '')
  current_group_required_action = $CurrentRequiredAction
  current_group_missing_fields = @($CurrentMissingFields)
  current_group_invalid_fields = @($CurrentInvalidFields)
  current_group_blocking_signals = @($CurrentBlockingSignals)
  measurement_capture_total_groups = [int](Get-PayloadValue -Payload $IntakeGate.payload -Name 'measurement_capture_total_groups' -Default 0)
  measurement_capture_ready_groups = [int](Get-PayloadValue -Payload $IntakeGate.payload -Name 'measurement_capture_ready_groups' -Default 0)
  measurement_capture_pending_groups = [int](Get-PayloadValue -Payload $IntakeGate.payload -Name 'measurement_capture_pending_groups' -Default 0)
  measurement_capture_invalid_groups = [int](Get-PayloadValue -Payload $IntakeGate.payload -Name 'measurement_capture_invalid_groups' -Default 0)
  measurement_capture_failed_groups = [int](Get-PayloadValue -Payload $IntakeGate.payload -Name 'measurement_capture_failed_groups' -Default 0)
  next_required_physical_input = [string](Get-PayloadValue -Payload $IntakeGate.payload -Name 'next_required_physical_input' -Default '')
  next_operator_action = $NextOperatorAction
  operator_sequence = @(
    'create_pending_measurement_record_with_fr017-new-measurement-record.ps1',
    'update_setup_safety_brief_with_fr017-update-measurement-setup-record.ps1_when_pending_record_exists',
    'capture_setup_and_safety_brief_without_symptoms_or_compression',
    'capture_left_arm_numeric_measurements_with_second_pass_repeatability',
    'capture_right_arm_numeric_measurements_separately_with_second_pass_repeatability',
    'capture_left_right_landmark_and_no_pressure_zone_references',
    'capture_left_right_independence_and_full_symptom_screen',
    'rerun_fr017-measurement-intake.ps1_before_any_mockup_patterning'
  )
  safety_stop_conditions = @(
    'pain',
    'tingling',
    'numbness',
    'cold_fingers',
    'discoloration',
    'hand_weakness',
    'wrist_pain',
    'sharp_pressure',
    'reduced_finger_motion',
    'loss_of_grip_strength',
    'tool_not_metric_or_millimeter_capable',
    'tissue_or_wrist_bone_compression_required',
    'copied_left_right_values_or_references'
  )
  measurement_session_brief_contract = 'Read-only operator brief for the first FR-017 physical-input gate. It summarizes the next measurement capture group and stop conditions, but it does not record measurements, write files, mark physical validation complete, or clear FR-018.'
  physical_validation_complete = $false
  stage17_completion_claim_allowed = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  read_only_contract = $true
  writes_repo = $false
  writes_data = $false
  grants_execution_authority = $false
  grants_mutation_authority = $false
  no_fake_validation_lock = 'This brief can make the next physical-input action clearer, but only a real accepted measurement record can move measurement_intake. It never certifies FR-017 or clears FR-018.'
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
