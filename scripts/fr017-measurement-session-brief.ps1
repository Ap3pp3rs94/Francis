[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$MeasurementPath = '',

  [string]$CandidateMeasurementPath = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$MeasurementIntakeScript = Join-Path $PSScriptRoot 'fr017-measurement-intake.ps1'
$MeasurementInitializerScript = Join-Path $PSScriptRoot 'fr017-new-measurement-record.ps1'

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

function New-CurrentGroupUpdateHint {
  param(
    [string]$GroupId,
    [string]$ResolvedMeasurementPath,
    [object]$IntakePayload,
    [bool]$UsingTemplate,
    [bool]$IntakeReady,
    [bool]$IntakeFailed
  )

  $MeasurementPathArg = if ([string]::IsNullOrWhiteSpace($ResolvedMeasurementPath)) { '<measurement-record.json>' } else { $ResolvedMeasurementPath }
  $SetupUpdatePath = [string](Get-PayloadValue -Payload $IntakePayload -Name 'measurement_setup_update_path' -Default (Join-Path $RepoRoot 'scripts\fr017-update-measurement-setup-record.ps1'))
  $InitializerPath = [string](Get-PayloadValue -Payload $IntakePayload -Name 'measurement_record_initializer_path' -Default (Join-Path $RepoRoot 'scripts\fr017-new-measurement-record.ps1'))
  $MeasurementUpdatePath = [string](Get-PayloadValue -Payload $IntakePayload -Name 'measurement_record_update_path' -Default (Join-Path $RepoRoot 'scripts\fr017-update-measurement-record.ps1'))
  $LandmarkUpdatePath = [string](Get-PayloadValue -Payload $IntakePayload -Name 'measurement_landmark_update_path' -Default (Join-Path $RepoRoot 'scripts\fr017-update-landmark-record.ps1'))
  $IndependenceSafetyUpdatePath = [string](Get-PayloadValue -Payload $IntakePayload -Name 'measurement_independence_safety_update_path' -Default (Join-Path $RepoRoot 'scripts\fr017-update-independence-safety-record.ps1'))
  $MockupReadinessPath = Join-Path $RepoRoot 'scripts\fr017-mockup-readiness-gate.ps1'

  if ($IntakeFailed) {
    return [ordered]@{
      tool_path = ''
      command_template = ''
      contract = 'Stop the measurement session and resolve the failed measurement-intake condition before any mockup, powered, load-bearing, or FR-018 work.'
    }
  }

  if ($IntakeReady) {
    return [ordered]@{
      tool_path = $MockupReadinessPath
      command_template = '.\scripts\fr017-mockup-readiness-gate.ps1 -Mode Status -MeasurementPath "{0}"' -f $MeasurementPathArg
      contract = 'Read-only handoff to the non-powered mockup readiness gate. This does not mark physical validation complete or clear FR-018.'
    }
  }

  switch ($GroupId) {
    'setup_and_safety_brief' {
      if ($UsingTemplate) {
        return [ordered]@{
          tool_path = $InitializerPath
          command_template = '.\scripts\fr017-new-measurement-record.ps1 -Mode Create -OutputPath <measurement-record.json> -EvidenceDate YYYY-MM-DD -Observer "<observer>" -PilotId "<pilot-reference>" -MeasurementTool "flexible metric tape" -Method "flexible tape, no tissue compression" -Posture "arm relaxed, palm neutral unless otherwise noted" -ConfirmNoTissueCompressionUsed -ConfirmNoWristBoneCompressionUsed -ConfirmMetricToolUsed -ConfirmArmRelaxedPalmNeutralOrExceptionRecorded -ConfirmStopConditionsBriefed -ConditionNotes "<no tissue/no wrist-bone compression, metric tool, and stop briefing notes>"'
          contract = 'Creates a pending working record and may populate the setup/safety brief only with real operator-supplied values. It does not record left/right measurements, validate fit, or clear FR-018.'
        }
      }
      return [ordered]@{
        tool_path = $SetupUpdatePath
        command_template = '.\scripts\fr017-update-measurement-setup-record.ps1 -Mode UpdateSetup -MeasurementPath "{0}" -EvidenceDate YYYY-MM-DD -Observer "<observer>" -PilotId "<pilot-reference>" -MeasurementTool "flexible metric tape" -Method "flexible tape, no tissue compression" -Posture "arm relaxed, palm neutral unless otherwise noted" -ConfirmNoTissueCompressionUsed -ConfirmNoWristBoneCompressionUsed -ConfirmMetricToolUsed -ConfirmArmRelaxedPalmNeutralOrExceptionRecorded -ConfirmStopConditionsBriefed -ConditionNotes "<no tissue/no wrist-bone compression, metric tool, and stop briefing notes>"' -f $MeasurementPathArg
        contract = 'Updates setup/safety fields in an existing working record only. It does not record left/right measurements, validate fit, or clear FR-018.'
      }
    }
    'left_arm_numeric_measurement_passes' {
      return [ordered]@{
        tool_path = $MeasurementUpdatePath
        command_template = '.\scripts\fr017-update-measurement-record.ps1 -Mode UpdateSide -MeasurementPath "{0}" -Side left -ForearmCircumference25mmBelowElbowCrease <mm> -ForearmCircumferenceMidForearm <mm> -ForearmCircumference40mmAboveWristCrease <mm> -ForearmLengthElbowCreaseToWristCrease <mm> -OuterForearmUsablePanelLength <mm> -UpperStrapAllowedBandWidth <mm> -LowerStrapAllowedBandWidth <mm> -BoneRidgeReliefLength <mm> -InnerForearmNoPressureZoneWidth <mm> -WristClearanceGap <mm> -ConfirmSecondPassCompleted -MaxDeltaMm <0-5> -ConfirmAllRequiredMeasurementsWithin5mm' -f $MeasurementPathArg
        contract = 'Records real left-side numeric measurement passes only. It does not validate fit, approve fabrication, or clear FR-018.'
      }
    }
    'right_arm_numeric_measurement_passes' {
      return [ordered]@{
        tool_path = $MeasurementUpdatePath
        command_template = '.\scripts\fr017-update-measurement-record.ps1 -Mode UpdateSide -MeasurementPath "{0}" -Side right -ForearmCircumference25mmBelowElbowCrease <mm> -ForearmCircumferenceMidForearm <mm> -ForearmCircumference40mmAboveWristCrease <mm> -ForearmLengthElbowCreaseToWristCrease <mm> -OuterForearmUsablePanelLength <mm> -UpperStrapAllowedBandWidth <mm> -LowerStrapAllowedBandWidth <mm> -BoneRidgeReliefLength <mm> -InnerForearmNoPressureZoneWidth <mm> -WristClearanceGap <mm> -ConfirmSecondPassCompleted -MaxDeltaMm <0-5> -ConfirmAllRequiredMeasurementsWithin5mm' -f $MeasurementPathArg
        contract = 'Records real right-side numeric measurement passes only. It does not validate fit, approve fabrication, or clear FR-018.'
      }
    }
    'safety_critical_landmark_and_zone_references' {
      return [ordered]@{
        tool_path = $LandmarkUpdatePath
        command_template = '.\scripts\fr017-update-landmark-record.ps1 -Mode UpdateLandmarks -MeasurementPath "{0}" -LeftInnerElbowCreaseBoundary "<left reference>" -LeftWristBoneBoundary "<left reference>" -LeftRadiusRidgeRelief "<left reference>" -LeftUlnaRidgeRelief "<left reference>" -LeftOuterForearmCableRoute "<left reference>" -LeftQuickReleaseReachZone "<left reference>" -LeftGloveRemovalPath "<left reference>" -RightInnerElbowCreaseBoundary "<right reference>" -RightWristBoneBoundary "<right reference>" -RightRadiusRidgeRelief "<right reference>" -RightUlnaRidgeRelief "<right reference>" -RightOuterForearmCableRoute "<right reference>" -RightQuickReleaseReachZone "<right reference>" -RightGloveRemovalPath "<right reference>" -ConfirmInnerElbowCreaseBoundary -ConfirmWristBoneBoundary -ConfirmRadiusUlnaReliefPaths -ConfirmOuterForearmCableRoute -ConfirmQuickReleaseReachZone -ConfirmGloveRemovalPath -ConfirmSkinSafeMarkingUsed -LandmarkNotes "<side-specific skin-safe landmark notes>"' -f $MeasurementPathArg
        contract = 'Records real side-specific marked-zone references only. It does not validate fit, approve fabrication, or clear FR-018.'
      }
    }
    'left_right_independence_and_safety_screen' {
      return [ordered]@{
        tool_path = $IndependenceSafetyUpdatePath
        command_template = '.\scripts\fr017-update-independence-safety-record.ps1 -Mode UpdateIndependenceSafety -MeasurementPath "{0}" -ConfirmLeftArmMeasuredSeparately -ConfirmRightArmMeasuredSeparately -ConfirmSideLabelsVerified -ConfirmValuesNotCopiedBetweenSides -LeftMeasurementReference "<left reference>" -RightMeasurementReference "<right reference>" -IndependenceNotes "<separate left/right side-label notes>" -ConfirmNoPain -ConfirmNoTingling -ConfirmNoNumbness -ConfirmNoColdFingers -ConfirmNoDiscoloration -ConfirmNoHandWeakness -ConfirmNoWristPain -ConfirmNoSharpPressure -ConfirmNoReducedFingerMotion -ConfirmNoLossOfGripStrength' -f $MeasurementPathArg
        contract = 'Records real left/right independence confirmations and symptom screen only. Any observed symptom must stop FR-017 progression; this does not clear FR-018.'
      }
    }
    default {
      return [ordered]@{
        tool_path = ''
        command_template = ''
        contract = 'No current update command is available because no measurement capture group is blocking.'
      }
    }
  }
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
$ResolvedMeasurementPath = Resolve-BriefPath -Path $MeasurementPath
$ResolvedCandidateMeasurementPath = Resolve-BriefPath -Path $CandidateMeasurementPath
$UsingTemplate = if ($null -eq $IntakeGate.payload -or $null -eq $IntakeGate.payload.PSObject.Properties['using_template']) { [string]::IsNullOrWhiteSpace($MeasurementPath) } else { [bool]$IntakeGate.payload.using_template }

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
$CurrentGroupUpdateHint = New-CurrentGroupUpdateHint -GroupId $FirstBlockingGroupId -ResolvedMeasurementPath $ResolvedMeasurementPath -IntakePayload $IntakeGate.payload -UsingTemplate $UsingTemplate -IntakeReady $IntakeReady -IntakeFailed $IntakeFailed
$CurrentGroupPreflightToolPath = ''
$CurrentGroupPreflightCommandTemplate = ''
$CurrentGroupPreflightContract = ''
$CurrentGroupPreflightStatus = ''
$CurrentGroupPreflightExitCode = 0
$CurrentGroupPreflightParseOk = $false
$CurrentGroupPreflightReadOnlyContract = $false
$CurrentGroupPreflightTemplateExists = $false
$CurrentGroupPreflightTemplateParseOk = $false
$CurrentGroupPreflightCandidateOutputPathReady = $false
$CurrentGroupPreflightOutputPath = ''
$CurrentGroupPreflightOutputExists = $false
$CurrentGroupPreflightOutputParentExists = $false
$CurrentGroupPreflightWroteFile = $false
$CurrentGroupPreflightPhysicalValidationComplete = $false
$CurrentGroupPreflightFr018ImplementationCleared = $false
if (-not $IntakeFailed -and -not $IntakeReady -and $UsingTemplate -and $FirstBlockingGroupId -eq 'setup_and_safety_brief') {
  $InitializerPath = [string](Get-PayloadValue -Payload $IntakeGate.payload -Name 'measurement_record_initializer_path' -Default (Join-Path $RepoRoot 'scripts\fr017-new-measurement-record.ps1'))
  $CurrentGroupPreflightToolPath = $InitializerPath
  $PreflightOutputPathArg = if ([string]::IsNullOrWhiteSpace($ResolvedCandidateMeasurementPath)) { '<measurement-record.json>' } else { $ResolvedCandidateMeasurementPath }
  $CurrentGroupPreflightCommandTemplate = '.\scripts\fr017-new-measurement-record.ps1 -Mode Status -OutputPath "{0}"' -f $PreflightOutputPathArg
  $CurrentGroupPreflightContract = 'Read-only initializer preflight for the pending measurement record. It checks the template and candidate output path, writes no evidence, records no measurements, and does not clear FR-018.'
  $PreflightArgs = @('-Mode', 'Status')
  if (-not [string]::IsNullOrWhiteSpace($ResolvedCandidateMeasurementPath)) {
    $PreflightArgs += @('-OutputPath', $ResolvedCandidateMeasurementPath)
  }
  $PreflightGate = Invoke-JsonGate -ScriptPath $MeasurementInitializerScript -Arguments $PreflightArgs
  $CurrentGroupPreflightExitCode = [int]$PreflightGate.exit_code
  $CurrentGroupPreflightParseOk = [bool]$PreflightGate.parse_ok
  $CurrentGroupPreflightStatus = if ([bool]$PreflightGate.parse_ok) { [string](Get-PayloadValue -Payload $PreflightGate.payload -Name 'status' -Default '') } else { 'failed_preflight_parse' }
  $CurrentGroupPreflightReadOnlyContract = [bool](Get-PayloadValue -Payload $PreflightGate.payload -Name 'read_only_contract' -Default $false)
  $CurrentGroupPreflightTemplateExists = [bool](Get-PayloadValue -Payload $PreflightGate.payload -Name 'template_exists' -Default $false)
  $CurrentGroupPreflightTemplateParseOk = [bool](Get-PayloadValue -Payload $PreflightGate.payload -Name 'template_parse_ok' -Default $false)
  $CurrentGroupPreflightCandidateOutputPathReady = [bool](Get-PayloadValue -Payload $PreflightGate.payload -Name 'candidate_output_path_ready' -Default $false)
  $CurrentGroupPreflightOutputPath = [string](Get-PayloadValue -Payload $PreflightGate.payload -Name 'output_path' -Default '')
  $CurrentGroupPreflightOutputExists = [bool](Get-PayloadValue -Payload $PreflightGate.payload -Name 'output_exists' -Default $false)
  $CurrentGroupPreflightOutputParentExists = [bool](Get-PayloadValue -Payload $PreflightGate.payload -Name 'output_parent_exists' -Default $false)
  $CurrentGroupPreflightWroteFile = [bool](Get-PayloadValue -Payload $PreflightGate.payload -Name 'wrote_file' -Default $false)
  $CurrentGroupPreflightPhysicalValidationComplete = [bool](Get-PayloadValue -Payload $PreflightGate.payload -Name 'physical_validation_complete' -Default $false)
  $CurrentGroupPreflightFr018ImplementationCleared = [bool](Get-PayloadValue -Payload $PreflightGate.payload -Name 'fr018_implementation_cleared' -Default $false)
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
  measurement_path = $ResolvedMeasurementPath
  candidate_measurement_path = $ResolvedCandidateMeasurementPath
  using_template = $UsingTemplate
  first_blocking_group_id = $FirstBlockingGroupId
  first_blocking_group_status = [string](Get-PayloadValue -Payload $IntakeGate.payload -Name 'measurement_capture_first_blocking_group_status' -Default '')
  first_blocking_group_action = [string](Get-PayloadValue -Payload $IntakeGate.payload -Name 'measurement_capture_first_blocking_group_action' -Default '')
  current_group_required_action = $CurrentRequiredAction
  current_group_missing_fields = @($CurrentMissingFields)
  current_group_invalid_fields = @($CurrentInvalidFields)
  current_group_blocking_signals = @($CurrentBlockingSignals)
  current_group_preflight_tool_path = $CurrentGroupPreflightToolPath
  current_group_preflight_command_template = $CurrentGroupPreflightCommandTemplate
  current_group_preflight_contract = $CurrentGroupPreflightContract
  current_group_preflight_status = $CurrentGroupPreflightStatus
  current_group_preflight_exit_code = $CurrentGroupPreflightExitCode
  current_group_preflight_parse_ok = $CurrentGroupPreflightParseOk
  current_group_preflight_read_only_contract = $CurrentGroupPreflightReadOnlyContract
  current_group_preflight_template_exists = $CurrentGroupPreflightTemplateExists
  current_group_preflight_template_parse_ok = $CurrentGroupPreflightTemplateParseOk
  current_group_preflight_candidate_output_path_ready = $CurrentGroupPreflightCandidateOutputPathReady
  current_group_preflight_output_path = $CurrentGroupPreflightOutputPath
  current_group_preflight_output_exists = $CurrentGroupPreflightOutputExists
  current_group_preflight_output_parent_exists = $CurrentGroupPreflightOutputParentExists
  current_group_preflight_wrote_file = $CurrentGroupPreflightWroteFile
  current_group_preflight_physical_validation_complete = $CurrentGroupPreflightPhysicalValidationComplete
  current_group_preflight_fr018_implementation_cleared = $CurrentGroupPreflightFr018ImplementationCleared
  current_group_update_tool_path = [string]$CurrentGroupUpdateHint.tool_path
  current_group_update_command_template = [string]$CurrentGroupUpdateHint.command_template
  current_group_update_contract = [string]$CurrentGroupUpdateHint.contract
  measurement_capture_total_groups = [int](Get-PayloadValue -Payload $IntakeGate.payload -Name 'measurement_capture_total_groups' -Default 0)
  measurement_capture_ready_groups = [int](Get-PayloadValue -Payload $IntakeGate.payload -Name 'measurement_capture_ready_groups' -Default 0)
  measurement_capture_pending_groups = [int](Get-PayloadValue -Payload $IntakeGate.payload -Name 'measurement_capture_pending_groups' -Default 0)
  measurement_capture_invalid_groups = [int](Get-PayloadValue -Payload $IntakeGate.payload -Name 'measurement_capture_invalid_groups' -Default 0)
  measurement_capture_failed_groups = [int](Get-PayloadValue -Payload $IntakeGate.payload -Name 'measurement_capture_failed_groups' -Default 0)
  next_required_physical_input = [string](Get-PayloadValue -Payload $IntakeGate.payload -Name 'next_required_physical_input' -Default '')
  next_operator_action = $NextOperatorAction
  operator_sequence = @(
    'preflight_measurement_record_initializer_status_with_fr017-new-measurement-record.ps1',
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
