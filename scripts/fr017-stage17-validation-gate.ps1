[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$ManifestPath = '',

  [string]$GateScriptRoot = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Resolve-GatePath {
  param([string]$Path)

  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Path))
}

function New-GateCheck {
  param(
    [string]$Id,
    [bool]$Passed,
    [string]$Evidence,
    [string]$Reason = ''
  )

  return [ordered]@{
    id = $Id
    passed = $Passed
    status = if ($Passed) { 'passed' } else { 'failed' }
    evidence = $Evidence
    reason = $Reason
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

function Test-MissingOrPendingText {
  param([object]$Value)

  if ($null -eq $Value) {
    return $true
  }
  $Text = ([string]$Value).Trim()
  return [string]::IsNullOrWhiteSpace($Text) -or [string]::Equals($Text, 'PENDING', [System.StringComparison]::OrdinalIgnoreCase)
}

function Read-GateText {
  param([string]$Path)

  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return ''
  }
  return [System.IO.File]::ReadAllText($Path)
}

function Add-MissingObjectProperties {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [object]$Payload,
    [string]$Prefix,
    [string[]]$Fields
  )

  foreach ($Field in $Fields) {
    if ($null -eq $Payload -or $null -eq $Payload.PSObject.Properties[$Field]) {
      $Target.Add(('{0}.{1}' -f $Prefix, $Field)) | Out-Null
    }
  }
}

function Add-MissingContractTextProperties {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [object]$Payload,
    [string[]]$Fields
  )

  foreach ($Field in $Fields) {
    $Value = if ($null -ne $Payload -and $null -ne $Payload.PSObject.Properties[$Field]) {
      [string]$Payload.PSObject.Properties[$Field].Value
    } else {
      ''
    }
    if (Test-MissingOrPendingText -Value $Value) {
      $Target.Add($Field) | Out-Null
    }
  }
}

$ResolvedManifestPath = if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
  Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-STAGE17-PACKAGE-MANIFEST.json'
} else {
  Resolve-GatePath -Path $ManifestPath
}
$ResolvedGateScriptRoot = if ([string]::IsNullOrWhiteSpace($GateScriptRoot)) {
  $PSScriptRoot
} else {
  Resolve-GatePath -Path $GateScriptRoot
}

$Checks = New-Object System.Collections.Generic.List[object]
$Manifest = $null
$ManifestExists = Test-Path -LiteralPath $ResolvedManifestPath -PathType Leaf
$Checks.Add((New-GateCheck -Id 'manifest_exists' -Passed $ManifestExists -Evidence $ResolvedManifestPath -Reason 'The FR-017 validation gate requires the Stage 17 package manifest.')) | Out-Null

if ($ManifestExists) {
  try {
    $Manifest = Get-Content -LiteralPath $ResolvedManifestPath -Raw | ConvertFrom-Json -ErrorAction Stop
    $Checks.Add((New-GateCheck -Id 'manifest_parse' -Passed $true -Evidence $ResolvedManifestPath)) | Out-Null
  } catch {
    $Checks.Add((New-GateCheck -Id 'manifest_parse' -Passed $false -Evidence $ResolvedManifestPath -Reason $_.Exception.Message)) | Out-Null
  }
} else {
  $Checks.Add((New-GateCheck -Id 'manifest_parse' -Passed $false -Evidence $ResolvedManifestPath -Reason 'Manifest path is missing.')) | Out-Null
}

$PackageRoot = Split-Path -Parent $ResolvedManifestPath
$RecordCount = 0
$CustomRecordCount = 0
$MissingRecordPaths = New-Object System.Collections.Generic.List[string]
$FailedPendingRecords = New-Object System.Collections.Generic.List[string]
$MissingCustomRecords = New-Object System.Collections.Generic.List[string]
$MissingMeasurementTemplateContracts = New-Object System.Collections.Generic.List[string]
$MissingMeasurementTemplateFields = New-Object System.Collections.Generic.List[string]
$MissingMockupTemplateContracts = New-Object System.Collections.Generic.List[string]
$MissingMockupTemplateFields = New-Object System.Collections.Generic.List[string]
$MissingMannequinTemplateContracts = New-Object System.Collections.Generic.List[string]
$MissingMannequinTemplateFields = New-Object System.Collections.Generic.List[string]
$MissingStaticFitTemplateContracts = New-Object System.Collections.Generic.List[string]
$MissingStaticFitTemplateFields = New-Object System.Collections.Generic.List[string]
$MissingMovementTemplateContracts = New-Object System.Collections.Generic.List[string]
$MissingMovementTemplateFields = New-Object System.Collections.Generic.List[string]
$MissingReleaseCableTemplateContracts = New-Object System.Collections.Generic.List[string]
$MissingReleaseCableTemplateFields = New-Object System.Collections.Generic.List[string]
$MissingEngineeringTemplateContracts = New-Object System.Collections.Generic.List[string]
$MissingEngineeringTemplateFields = New-Object System.Collections.Generic.List[string]
$MissingFinalDecisionTemplateContracts = New-Object System.Collections.Generic.List[string]
$MissingFinalDecisionTemplateFields = New-Object System.Collections.Generic.List[string]
$MissingGateScripts = New-Object System.Collections.Generic.List[string]
$InvalidGateScripts = New-Object System.Collections.Generic.List[string]
$BlockedInputs = @()
$SafetyFailConditions = @()
$PhysicalValidation = ''
$Fr018Status = ''
$RequiredGateScripts = @(
  'fr017-stage17-validation-gate.ps1',
  'fr017-measurement-intake.ps1',
  'fr017-mockup-readiness-gate.ps1',
  'fr017-mannequin-interface-gate.ps1',
  'fr017-pilot-static-fit-gate.ps1',
  'fr017-pilot-movement-gate.ps1',
  'fr017-quick-release-cable-snag-gate.ps1',
  'fr017-engineering-review-gate.ps1',
  'fr017-final-physical-gate.ps1',
  'fr017-final-decision-record-gate.ps1',
  'fr017-evidence-chain-status.ps1'
)

if ($null -ne $Manifest) {
  $PhysicalValidation = [string]$Manifest.status.physical_validation
  $Fr018Status = [string]$Manifest.status.fr_018_implementation
  $BlockedInputs = ConvertTo-StringArray -Value $Manifest.blocked_inputs
  $SafetyFailConditions = ConvertTo-StringArray -Value $Manifest.safety_fail_conditions
  $Records = @($Manifest.records)
  $RecordCount = $Records.Count
  $CustomRecords = ConvertTo-StringArray -Value $Manifest.custom_records
  $CustomRecordCount = $CustomRecords.Count

  $Checks.Add((New-GateCheck -Id 'package_id' -Passed ([string]$Manifest.package_id -eq 'FR-017-STAGE17') -Evidence ([string]$Manifest.package_id))) | Out-Null
  $Checks.Add((New-GateCheck -Id 'component' -Passed ([string]$Manifest.component -eq 'FR-017 Forearm Cuffs') -Evidence ([string]$Manifest.component))) | Out-Null
  $Checks.Add((New-GateCheck -Id 'documentation_complete' -Passed ([string]$Manifest.status.documentation -eq 'complete') -Evidence ([string]$Manifest.status.documentation))) | Out-Null
  $Checks.Add((New-GateCheck -Id 'evidence_containers_complete' -Passed ([string]$Manifest.status.evidence_containers -eq 'complete') -Evidence ([string]$Manifest.status.evidence_containers))) | Out-Null
  $Checks.Add((New-GateCheck -Id 'physical_validation_blocked' -Passed ($PhysicalValidation -eq 'not_complete') -Evidence $PhysicalValidation -Reason 'Physical validation must remain blocked until measurement, mannequin, pilot, release, cable, and engineering evidence exists.')) | Out-Null
  $Checks.Add((New-GateCheck -Id 'fr018_not_cleared' -Passed ($Fr018Status -eq 'not_cleared') -Evidence $Fr018Status -Reason 'FR-018 implementation must remain blocked until FR-017 physical blockers are evidence-cleared.')) | Out-Null
  $Checks.Add((New-GateCheck -Id 'record_count' -Passed ($RecordCount -eq 23) -Evidence ([string]$RecordCount))) | Out-Null
  $Checks.Add((New-GateCheck -Id 'custom_record_count' -Passed ($CustomRecordCount -eq 19) -Evidence ([string]$CustomRecordCount))) | Out-Null

  foreach ($Record in $Records) {
    $RecordPath = [System.IO.Path]::GetFullPath((Join-Path $PackageRoot ([string]$Record.path)))
    if (-not (Test-Path -LiteralPath $RecordPath -PathType Leaf)) {
      $MissingRecordPaths.Add([string]$Record.path) | Out-Null
    }
    $RecordStatus = [string]$Record.status
    if ($RecordStatus.StartsWith('requires_')) {
      $RecordText = Read-GateText -Path $RecordPath
      $HasPending = $RecordText.Contains('PENDING')
      $HasUntested = $RecordText.Contains('NOT TESTED') -or $RecordText.Contains('REQUIRES MEASUREMENT')
      $HasUnvalidated = $RecordText.Contains('NOT VALIDATED') -or $RecordText.Contains('No measurements have been entered.')
      if (-not ($HasPending -and $HasUntested -and $HasUnvalidated)) {
        $FailedPendingRecords.Add([string]$Record.path) | Out-Null
      }
    }
  }
  $Checks.Add((New-GateCheck -Id 'manifest_record_paths_resolve' -Passed ($MissingRecordPaths.Count -eq 0) -Evidence (($MissingRecordPaths.ToArray() -join ', ')))) | Out-Null
  $Checks.Add((New-GateCheck -Id 'pending_records_keep_no_fake_validation_language' -Passed ($FailedPendingRecords.Count -eq 0) -Evidence (($FailedPendingRecords.ToArray() -join ', ')))) | Out-Null

  $ManualRecord = @($Records | Where-Object { [string]$_.kind -eq 'master_manual' } | Select-Object -First 1)
  $MapsRecord = @($Records | Where-Object { [string]$_.kind -eq 'maps_layouts_rollup' } | Select-Object -First 1)
  $MeasurementTemplateRecord = @($Records | Where-Object { [string]$_.kind -eq 'measurement_input_template' } | Select-Object -First 1)
  $MockupTemplateRecord = @($Records | Where-Object { [string]$_.kind -eq 'mockup_build_input_template' } | Select-Object -First 1)
  $MannequinTemplateRecord = @($Records | Where-Object { [string]$_.kind -eq 'mannequin_interface_input_template' } | Select-Object -First 1)
  $StaticFitTemplateRecord = @($Records | Where-Object { [string]$_.kind -eq 'pilot_static_fit_input_template' } | Select-Object -First 1)
  $MovementTemplateRecord = @($Records | Where-Object { [string]$_.kind -eq 'pilot_movement_input_template' } | Select-Object -First 1)
  $ReleaseCableTemplateRecord = @($Records | Where-Object { [string]$_.kind -eq 'quick_release_cable_snag_input_template' } | Select-Object -First 1)
  $EngineeringTemplateRecord = @($Records | Where-Object { [string]$_.kind -eq 'engineering_review_input_template' } | Select-Object -First 1)
  $FinalDecisionTemplateRecord = @($Records | Where-Object { [string]$_.kind -eq 'final_physical_decision_input_template' } | Select-Object -First 1)
  $ManualPath = if ($ManualRecord.Count -gt 0) { [System.IO.Path]::GetFullPath((Join-Path $PackageRoot ([string]$ManualRecord[0].path))) } else { '' }
  $MapsPath = if ($MapsRecord.Count -gt 0) { [System.IO.Path]::GetFullPath((Join-Path $PackageRoot ([string]$MapsRecord[0].path))) } else { '' }
  $MeasurementTemplatePath = if ($MeasurementTemplateRecord.Count -gt 0) { [System.IO.Path]::GetFullPath((Join-Path $PackageRoot ([string]$MeasurementTemplateRecord[0].path))) } else { '' }
  $MockupTemplatePath = if ($MockupTemplateRecord.Count -gt 0) { [System.IO.Path]::GetFullPath((Join-Path $PackageRoot ([string]$MockupTemplateRecord[0].path))) } else { '' }
  $MannequinTemplatePath = if ($MannequinTemplateRecord.Count -gt 0) { [System.IO.Path]::GetFullPath((Join-Path $PackageRoot ([string]$MannequinTemplateRecord[0].path))) } else { '' }
  $StaticFitTemplatePath = if ($StaticFitTemplateRecord.Count -gt 0) { [System.IO.Path]::GetFullPath((Join-Path $PackageRoot ([string]$StaticFitTemplateRecord[0].path))) } else { '' }
  $MovementTemplatePath = if ($MovementTemplateRecord.Count -gt 0) { [System.IO.Path]::GetFullPath((Join-Path $PackageRoot ([string]$MovementTemplateRecord[0].path))) } else { '' }
  $ReleaseCableTemplatePath = if ($ReleaseCableTemplateRecord.Count -gt 0) { [System.IO.Path]::GetFullPath((Join-Path $PackageRoot ([string]$ReleaseCableTemplateRecord[0].path))) } else { '' }
  $EngineeringTemplatePath = if ($EngineeringTemplateRecord.Count -gt 0) { [System.IO.Path]::GetFullPath((Join-Path $PackageRoot ([string]$EngineeringTemplateRecord[0].path))) } else { '' }
  $FinalDecisionTemplatePath = if ($FinalDecisionTemplateRecord.Count -gt 0) { [System.IO.Path]::GetFullPath((Join-Path $PackageRoot ([string]$FinalDecisionTemplateRecord[0].path))) } else { '' }
  $CustomRecordText = (Read-GateText -Path $ManualPath) + "`n" + (Read-GateText -Path $MapsPath)
  foreach ($Index in 1..19) {
    $ExpectedId = 'FR-017-CUSTOM-{0:D3}' -f $Index
    if (-not $CustomRecordText.Contains($ExpectedId)) {
      $MissingCustomRecords.Add($ExpectedId) | Out-Null
    }
  }
  $Checks.Add((New-GateCheck -Id 'custom_records_present_in_package_text' -Passed ($MissingCustomRecords.Count -eq 0) -Evidence (($MissingCustomRecords.ToArray() -join ', ')))) | Out-Null

  $MeasurementTemplate = $null
  $MeasurementTemplateParsed = $false
  if (-not [string]::IsNullOrWhiteSpace($MeasurementTemplatePath) -and (Test-Path -LiteralPath $MeasurementTemplatePath -PathType Leaf)) {
    try {
      $MeasurementTemplate = Get-Content -LiteralPath $MeasurementTemplatePath -Raw | ConvertFrom-Json -ErrorAction Stop
      $MeasurementTemplateParsed = $true
    } catch {
      $MeasurementTemplateParsed = $false
    }
  }
  $Checks.Add((New-GateCheck -Id 'measurement_input_template_parse' -Passed $MeasurementTemplateParsed -Evidence $MeasurementTemplatePath -Reason 'The measurement intake template must parse before package validation can trust its required field contract.')) | Out-Null
  $RequiredMeasurementTemplateContracts = @(
    'units',
    'evidence_date',
    'measurement_tool',
    'measurement_tool_exclusions',
    'measurement_method',
    'measurement_method_exclusions',
    'measurement_posture',
    'measurement_posture_exclusions',
    'placeholder_values',
    'numeric_measurements',
    'measurement_bounds',
    'measurement_consistency',
    'marked_zone_specificity',
    'left_right_independence',
    'measurement_conditions',
    'landmark_confirmation',
    'measurement_notes',
    'repeatability',
    'safety_screen'
  )
  $FieldContractPayload = if ($MeasurementTemplateParsed) { $MeasurementTemplate.field_contract } else { $null }
  foreach ($Field in $RequiredMeasurementTemplateContracts) {
    $Value = if ($null -ne $FieldContractPayload -and $null -ne $FieldContractPayload.PSObject.Properties[$Field]) {
      [string]$FieldContractPayload.PSObject.Properties[$Field].Value
    } else {
      ''
    }
    if (Test-MissingOrPendingText -Value $Value) {
      $MissingMeasurementTemplateContracts.Add($Field) | Out-Null
    }
  }
  $Checks.Add((New-GateCheck -Id 'measurement_input_template_contracts' -Passed ($MissingMeasurementTemplateContracts.Count -eq 0) -Evidence (($MissingMeasurementTemplateContracts.ToArray() -join ', ')) -Reason 'Measurement intake template must preserve all field contracts required by the intake gate.')) | Out-Null

  $RequiredMeasurementFields = @(
    'forearm_circumference_25mm_below_elbow_crease',
    'forearm_circumference_mid_forearm',
    'forearm_circumference_40mm_above_wrist_crease',
    'forearm_length_elbow_crease_to_wrist_crease',
    'outer_forearm_usable_panel_length',
    'upper_strap_allowed_band_width',
    'lower_strap_allowed_band_width',
    'bone_ridge_relief_length',
    'inner_forearm_no_pressure_zone_width',
    'wrist_clearance_gap'
  )
  $RequiredMarkedZoneFields = @(
    'inner_elbow_crease_boundary',
    'wrist_bone_boundary',
    'radius_ridge_relief',
    'ulna_ridge_relief',
    'outer_forearm_cable_route',
    'quick_release_reach_zone',
    'glove_removal_path'
  )
  $RequiredRepeatabilityFields = @(
    'second_pass_completed',
    'max_delta_mm',
    'all_required_measurements_within_5mm'
  )
  $RequiredLeftRightIndependenceFields = @(
    'left_arm_measured_separately',
    'right_arm_measured_separately',
    'side_labels_verified',
    'values_not_copied_between_sides',
    'left_measurement_reference',
    'right_measurement_reference',
    'independence_notes'
  )
  $RequiredMeasurementConditionFields = @(
    'no_tissue_compression_used',
    'no_wrist_bone_compression_used',
    'metric_tool_used',
    'arm_relaxed_palm_neutral_or_exception_recorded',
    'stop_conditions_briefed',
    'condition_notes'
  )
  $RequiredLandmarkConfirmationFields = @(
    'inner_elbow_crease_boundary_confirmed',
    'wrist_bone_boundary_confirmed',
    'radius_ulna_relief_paths_confirmed',
    'outer_forearm_cable_route_confirmed',
    'quick_release_reach_zone_confirmed',
    'glove_removal_path_confirmed',
    'skin_safe_marking_used',
    'landmark_notes'
  )
  $RequiredSafetyScreenFields = @(
    'pain',
    'tingling',
    'numbness',
    'cold_fingers',
    'discoloration',
    'hand_weakness',
    'wrist_pain',
    'sharp_pressure',
    'reduced_finger_motion',
    'loss_of_grip_strength'
  )

  $SidesPayload = if ($MeasurementTemplateParsed) { $MeasurementTemplate.sides } else { $null }
  $MarkedZonesPayload = if ($MeasurementTemplateParsed) { $MeasurementTemplate.marked_zones } else { $null }
  $RepeatabilityPayload = if ($MeasurementTemplateParsed) { $MeasurementTemplate.repeatability } else { $null }
  foreach ($Side in @('left', 'right')) {
    $SideMeasurementsPayload = $null
    $SideMarkedZonesPayload = $null
    $SideRepeatabilityPayload = $null
    if ($null -ne $SidesPayload -and $null -ne $SidesPayload.PSObject.Properties[$Side]) {
      $SideMeasurementsPayload = $SidesPayload.PSObject.Properties[$Side].Value
    }
    if ($null -ne $MarkedZonesPayload -and $null -ne $MarkedZonesPayload.PSObject.Properties[$Side]) {
      $SideMarkedZonesPayload = $MarkedZonesPayload.PSObject.Properties[$Side].Value
    }
    if ($null -ne $RepeatabilityPayload -and $null -ne $RepeatabilityPayload.PSObject.Properties[$Side]) {
      $SideRepeatabilityPayload = $RepeatabilityPayload.PSObject.Properties[$Side].Value
    }

    Add-MissingObjectProperties -Target $MissingMeasurementTemplateFields -Payload $SideMeasurementsPayload -Prefix ('sides.{0}' -f $Side) -Fields $RequiredMeasurementFields
    Add-MissingObjectProperties -Target $MissingMeasurementTemplateFields -Payload $SideMarkedZonesPayload -Prefix ('marked_zones.{0}' -f $Side) -Fields $RequiredMarkedZoneFields
    Add-MissingObjectProperties -Target $MissingMeasurementTemplateFields -Payload $SideRepeatabilityPayload -Prefix ('repeatability.{0}' -f $Side) -Fields $RequiredRepeatabilityFields
  }
  $LeftRightIndependencePayload = if ($MeasurementTemplateParsed) { $MeasurementTemplate.left_right_independence } else { $null }
  $MeasurementConditionsPayload = if ($MeasurementTemplateParsed) { $MeasurementTemplate.measurement_conditions } else { $null }
  $LandmarkConfirmationPayload = if ($MeasurementTemplateParsed) { $MeasurementTemplate.landmark_confirmation } else { $null }
  $SafetyScreenPayload = if ($MeasurementTemplateParsed) { $MeasurementTemplate.safety_screen } else { $null }
  Add-MissingObjectProperties -Target $MissingMeasurementTemplateFields -Payload $LeftRightIndependencePayload -Prefix 'left_right_independence' -Fields $RequiredLeftRightIndependenceFields
  Add-MissingObjectProperties -Target $MissingMeasurementTemplateFields -Payload $MeasurementConditionsPayload -Prefix 'measurement_conditions' -Fields $RequiredMeasurementConditionFields
  Add-MissingObjectProperties -Target $MissingMeasurementTemplateFields -Payload $LandmarkConfirmationPayload -Prefix 'landmark_confirmation' -Fields $RequiredLandmarkConfirmationFields
  Add-MissingObjectProperties -Target $MissingMeasurementTemplateFields -Payload $SafetyScreenPayload -Prefix 'safety_screen' -Fields $RequiredSafetyScreenFields
  $Checks.Add((New-GateCheck -Id 'measurement_input_template_required_fields' -Passed ($MissingMeasurementTemplateFields.Count -eq 0) -Evidence (($MissingMeasurementTemplateFields.ToArray() -join ', ')) -Reason 'Measurement intake template must keep every field required by the measurement intake gate.')) | Out-Null

  $MockupTemplate = $null
  $MockupTemplateParsed = $false
  if (-not [string]::IsNullOrWhiteSpace($MockupTemplatePath) -and (Test-Path -LiteralPath $MockupTemplatePath -PathType Leaf)) {
    try {
      $MockupTemplate = Get-Content -LiteralPath $MockupTemplatePath -Raw | ConvertFrom-Json -ErrorAction Stop
      $MockupTemplateParsed = $true
    } catch {
      $MockupTemplateParsed = $false
    }
  }
  $Checks.Add((New-GateCheck -Id 'mockup_input_template_parse' -Passed $MockupTemplateParsed -Evidence $MockupTemplatePath -Reason 'The mockup input template must parse before package validation can trust its required field contract.')) | Out-Null
  $RequiredMockupTemplateContracts = @(
    'evidence_date',
    'placeholder_values',
    'evidence_chronology',
    'build_method',
    'record_linkage',
    'materials',
    'constraints',
    'side_checks'
  )
  $MockupContractPayload = if ($MockupTemplateParsed) { $MockupTemplate.field_contract } else { $null }
  foreach ($Field in $RequiredMockupTemplateContracts) {
    $Value = if ($null -ne $MockupContractPayload -and $null -ne $MockupContractPayload.PSObject.Properties[$Field]) {
      [string]$MockupContractPayload.PSObject.Properties[$Field].Value
    } else {
      ''
    }
    if (Test-MissingOrPendingText -Value $Value) {
      $MissingMockupTemplateContracts.Add($Field) | Out-Null
    }
  }
  $Checks.Add((New-GateCheck -Id 'mockup_input_template_contracts' -Passed ($MissingMockupTemplateContracts.Count -eq 0) -Evidence (($MissingMockupTemplateContracts.ToArray() -join ', ')) -Reason 'Mockup input template must preserve all field contracts required by the mockup readiness gate.')) | Out-Null

  $RequiredMockupEvidenceFields = @(
    'date',
    'observer',
    'build_method',
    'measurement_record_path'
  )
  $RequiredMockupMaterialFields = @(
    'padding_layer',
    'semi_rigid_outer_layer',
    'upper_forearm_strap',
    'lower_forearm_strap',
    'quick_release',
    'outer_forearm_cable_sleeve',
    'non_load_bearing_alignment_tabs',
    'sensor_placeholder_blanks'
  )
  $RequiredMockupConstraintFields = @(
    'non_powered_only',
    'no_load_bearing_claim',
    'no_hard_inner_forearm_buckles',
    'no_inner_elbow_crossing',
    'no_wrist_bone_pressure',
    'releases_visible_and_reachable',
    'glove_removal_path_preserved',
    'outer_forearm_cable_route_only',
    'stop_on_symptoms'
  )
  $RequiredMockupSideCheckFields = @(
    'upper_strap_width_matches_measurement',
    'lower_strap_width_matches_measurement',
    'bone_relief_channel_present',
    'inner_forearm_no_pressure_zone_marked',
    'wrist_clearance_kept',
    'quick_release_installed_outer_or_lateral',
    'alignment_tabs_non_load_bearing',
    'cable_sleeve_outer_route_only'
  )
  $MockupEvidencePayload = if ($MockupTemplateParsed) { $MockupTemplate.evidence } else { $null }
  $MockupMaterialsPayload = if ($MockupTemplateParsed) { $MockupTemplate.materials } else { $null }
  $MockupConstraintsPayload = if ($MockupTemplateParsed) { $MockupTemplate.constraints } else { $null }
  Add-MissingObjectProperties -Target $MissingMockupTemplateFields -Payload $MockupEvidencePayload -Prefix 'evidence' -Fields $RequiredMockupEvidenceFields
  Add-MissingObjectProperties -Target $MissingMockupTemplateFields -Payload $MockupMaterialsPayload -Prefix 'materials' -Fields $RequiredMockupMaterialFields
  Add-MissingObjectProperties -Target $MissingMockupTemplateFields -Payload $MockupConstraintsPayload -Prefix 'constraints' -Fields $RequiredMockupConstraintFields
  $MockupSidesPayload = if ($MockupTemplateParsed) { $MockupTemplate.sides } else { $null }
  foreach ($Side in @('left', 'right')) {
    $MockupSidePayload = $null
    if ($null -ne $MockupSidesPayload -and $null -ne $MockupSidesPayload.PSObject.Properties[$Side]) {
      $MockupSidePayload = $MockupSidesPayload.PSObject.Properties[$Side].Value
    }
    Add-MissingObjectProperties -Target $MissingMockupTemplateFields -Payload $MockupSidePayload -Prefix ('sides.{0}' -f $Side) -Fields $RequiredMockupSideCheckFields
  }
  $Checks.Add((New-GateCheck -Id 'mockup_input_template_required_fields' -Passed ($MissingMockupTemplateFields.Count -eq 0) -Evidence (($MissingMockupTemplateFields.ToArray() -join ', ')) -Reason 'Mockup input template must keep every field required by the mockup readiness gate.')) | Out-Null

  $MannequinTemplate = $null
  $MannequinTemplateParsed = $false
  if (-not [string]::IsNullOrWhiteSpace($MannequinTemplatePath) -and (Test-Path -LiteralPath $MannequinTemplatePath -PathType Leaf)) {
    try {
      $MannequinTemplate = Get-Content -LiteralPath $MannequinTemplatePath -Raw | ConvertFrom-Json -ErrorAction Stop
      $MannequinTemplateParsed = $true
    } catch {
      $MannequinTemplateParsed = $false
    }
  }
  $Checks.Add((New-GateCheck -Id 'mannequin_input_template_parse' -Passed $MannequinTemplateParsed -Evidence $MannequinTemplatePath -Reason 'The mannequin interface template must parse before package validation can trust its required field contract.')) | Out-Null
  $RequiredMannequinTemplateContracts = @(
    'evidence_date',
    'placeholder_values',
    'test_subject',
    'record_linkage',
    'evidence_chronology',
    'required_pass_checks',
    'fail_observations'
  )
  $MannequinContractPayload = if ($MannequinTemplateParsed) { $MannequinTemplate.field_contract } else { $null }
  foreach ($Field in $RequiredMannequinTemplateContracts) {
    $Value = if ($null -ne $MannequinContractPayload -and $null -ne $MannequinContractPayload.PSObject.Properties[$Field]) {
      [string]$MannequinContractPayload.PSObject.Properties[$Field].Value
    } else {
      ''
    }
    if (Test-MissingOrPendingText -Value $Value) {
      $MissingMannequinTemplateContracts.Add($Field) | Out-Null
    }
  }
  $Checks.Add((New-GateCheck -Id 'mannequin_input_template_contracts' -Passed ($MissingMannequinTemplateContracts.Count -eq 0) -Evidence (($MissingMannequinTemplateContracts.ToArray() -join ', ')) -Reason 'Mannequin interface template must preserve all field contracts required by the mannequin gate.')) | Out-Null

  $RequiredMannequinEvidenceFields = @(
    'date',
    'observer',
    'mockup_readiness_record_path',
    'mannequin_or_arm_form_id',
    'future_interface_mock_geometry_revision',
    'cable_sleeve_mock_id'
  )
  $RequiredMannequinTestArticleFields = @(
    'left_cuff_revision',
    'right_cuff_revision',
    'non_powered_only'
  )
  $RequiredMannequinInterfaceIds = @(
    'fr032_left_forearm_frame',
    'fr033_right_forearm_frame',
    'fr043_left_elbow_joint',
    'fr044_right_elbow_joint',
    'fr045_left_wrist_joint',
    'fr046_right_wrist_joint',
    'fr066_left_glove_base',
    'fr067_right_glove_base',
    'fr068_palm_interface_ring',
    'fr184_forearm_armor'
  )
  $RequiredMannequinInterfaceFields = @(
    'mock_installed',
    'clearance_passed',
    'notes'
  )
  $RequiredMannequinCableSensorFields = @(
    'fr163_outer_route_only',
    'fr069_no_pressure_or_palm_crossing',
    'fr070_no_powered_anchoring',
    'fr145_no_raised_hard_spot',
    'fr149_no_pressure_zone_placement'
  )
  $RequiredMannequinReleaseFields = @(
    'left_release_visible_and_reachable',
    'right_release_visible_and_reachable',
    'armor_does_not_hide_release',
    'glove_and_wrist_removal_paths_open'
  )
  $RequiredMannequinFailObservationFields = @(
    'snag_detected',
    'compression_detected',
    'release_hidden',
    'wrist_path_blocked',
    'glove_path_blocked',
    'cable_inner_elbow_crossing',
    'cable_wrist_bone_crossing',
    'cable_palm_or_grip_crossing'
  )
  $MannequinEvidencePayload = if ($MannequinTemplateParsed) { $MannequinTemplate.evidence } else { $null }
  $MannequinTestArticlePayload = if ($MannequinTemplateParsed) { $MannequinTemplate.test_article } else { $null }
  $MannequinInterfacesPayload = if ($MannequinTemplateParsed) { $MannequinTemplate.interfaces } else { $null }
  $MannequinCableSensorPayload = if ($MannequinTemplateParsed) { $MannequinTemplate.cable_sensor_checks } else { $null }
  $MannequinReleasePayload = if ($MannequinTemplateParsed) { $MannequinTemplate.release_checks } else { $null }
  $MannequinFailObservationPayload = if ($MannequinTemplateParsed) { $MannequinTemplate.fail_observations } else { $null }
  Add-MissingObjectProperties -Target $MissingMannequinTemplateFields -Payload $MannequinEvidencePayload -Prefix 'evidence' -Fields $RequiredMannequinEvidenceFields
  Add-MissingObjectProperties -Target $MissingMannequinTemplateFields -Payload $MannequinTestArticlePayload -Prefix 'test_article' -Fields $RequiredMannequinTestArticleFields
  foreach ($InterfaceId in $RequiredMannequinInterfaceIds) {
    $InterfacePayload = $null
    if ($null -ne $MannequinInterfacesPayload -and $null -ne $MannequinInterfacesPayload.PSObject.Properties[$InterfaceId]) {
      $InterfacePayload = $MannequinInterfacesPayload.PSObject.Properties[$InterfaceId].Value
    }
    Add-MissingObjectProperties -Target $MissingMannequinTemplateFields -Payload $InterfacePayload -Prefix ('interfaces.{0}' -f $InterfaceId) -Fields $RequiredMannequinInterfaceFields
  }
  Add-MissingObjectProperties -Target $MissingMannequinTemplateFields -Payload $MannequinCableSensorPayload -Prefix 'cable_sensor_checks' -Fields $RequiredMannequinCableSensorFields
  Add-MissingObjectProperties -Target $MissingMannequinTemplateFields -Payload $MannequinReleasePayload -Prefix 'release_checks' -Fields $RequiredMannequinReleaseFields
  Add-MissingObjectProperties -Target $MissingMannequinTemplateFields -Payload $MannequinFailObservationPayload -Prefix 'fail_observations' -Fields $RequiredMannequinFailObservationFields
  $Checks.Add((New-GateCheck -Id 'mannequin_input_template_required_fields' -Passed ($MissingMannequinTemplateFields.Count -eq 0) -Evidence (($MissingMannequinTemplateFields.ToArray() -join ', ')) -Reason 'Mannequin interface template must keep every field required by the mannequin gate.')) | Out-Null

  $StaticFitTemplate = $null
  $StaticFitTemplateParsed = $false
  if (-not [string]::IsNullOrWhiteSpace($StaticFitTemplatePath) -and (Test-Path -LiteralPath $StaticFitTemplatePath -PathType Leaf)) {
    try {
      $StaticFitTemplate = Get-Content -LiteralPath $StaticFitTemplatePath -Raw | ConvertFrom-Json -ErrorAction Stop
      $StaticFitTemplateParsed = $true
    } catch {
      $StaticFitTemplateParsed = $false
    }
  }
  $Checks.Add((New-GateCheck -Id 'static_fit_input_template_parse' -Passed $StaticFitTemplateParsed -Evidence $StaticFitTemplatePath -Reason 'The pilot static-fit template must parse before package validation can trust its required field contract.')) | Out-Null
  $RequiredStaticFitTemplateContracts = @(
    'evidence_date',
    'placeholder_values',
    'pilot_identity_linkage',
    'record_linkage',
    'evidence_chronology',
    'test_duration',
    'required_pass_checks',
    'symptoms'
  )
  $StaticFitContractPayload = if ($StaticFitTemplateParsed) { $StaticFitTemplate.field_contract } else { $null }
  Add-MissingContractTextProperties -Target $MissingStaticFitTemplateContracts -Payload $StaticFitContractPayload -Fields $RequiredStaticFitTemplateContracts
  $Checks.Add((New-GateCheck -Id 'static_fit_input_template_contracts' -Passed ($MissingStaticFitTemplateContracts.Count -eq 0) -Evidence (($MissingStaticFitTemplateContracts.ToArray() -join ', ')) -Reason 'Pilot static-fit template must preserve all field contracts required by the static-fit gate.')) | Out-Null

  $RequiredStaticFitEvidenceFields = @(
    'date',
    'observer',
    'pilot_id',
    'prototype_revision',
    'measurement_record_path',
    'mockup_build_record_path',
    'mannequin_interface_record_path',
    'test_duration_minutes'
  )
  $RequiredStaticFitPreconditionFields = @(
    'non_powered_only',
    'no_frame_or_power_coupling',
    'observer_present',
    'emergency_release_briefed',
    'stop_on_symptoms',
    'pilot_can_self_remove_or_abort'
  )
  $RequiredStaticFitBaselineFields = @(
    'fingers_warm_before_donning',
    'normal_color_before_donning',
    'baseline_grip_present'
  )
  $RequiredStaticFitCheckFields = @(
    'cuff_below_elbow_crease',
    'lower_cuff_above_wrist_bones',
    'upper_strap_broad_non_compressive',
    'lower_strap_broad_non_compressive',
    'inner_forearm_clear',
    'bone_relief_present',
    'quick_release_visible_tactile_reachable',
    'cuff_stable_without_migration',
    'glove_removal_path_open',
    'wrist_assembly_removal_path_open',
    'cable_route_static_no_snag'
  )
  $RequiredStaticFitPostDoffFields = @(
    'fingers_warm_after_doffing',
    'normal_color_after_doffing',
    'grip_strength_unchanged'
  )
  $StaticFitEvidencePayload = if ($StaticFitTemplateParsed) { $StaticFitTemplate.evidence } else { $null }
  $StaticFitPreconditionsPayload = if ($StaticFitTemplateParsed) { $StaticFitTemplate.preconditions } else { $null }
  $StaticFitSidesPayload = if ($StaticFitTemplateParsed) { $StaticFitTemplate.sides } else { $null }
  Add-MissingObjectProperties -Target $MissingStaticFitTemplateFields -Payload $StaticFitEvidencePayload -Prefix 'evidence' -Fields $RequiredStaticFitEvidenceFields
  Add-MissingObjectProperties -Target $MissingStaticFitTemplateFields -Payload $StaticFitPreconditionsPayload -Prefix 'preconditions' -Fields $RequiredStaticFitPreconditionFields
  foreach ($Side in @('left', 'right')) {
    $StaticFitSidePayload = $null
    if ($null -ne $StaticFitSidesPayload -and $null -ne $StaticFitSidesPayload.PSObject.Properties[$Side]) {
      $StaticFitSidePayload = $StaticFitSidesPayload.PSObject.Properties[$Side].Value
    }
    $StaticFitBaselinePayload = if ($null -ne $StaticFitSidePayload) { $StaticFitSidePayload.baseline } else { $null }
    $StaticFitChecksPayload = if ($null -ne $StaticFitSidePayload) { $StaticFitSidePayload.static_checks } else { $null }
    $StaticFitPostDoffPayload = if ($null -ne $StaticFitSidePayload) { $StaticFitSidePayload.post_doff } else { $null }
    $StaticFitSymptomsPayload = if ($null -ne $StaticFitSidePayload) { $StaticFitSidePayload.symptoms } else { $null }
    Add-MissingObjectProperties -Target $MissingStaticFitTemplateFields -Payload $StaticFitBaselinePayload -Prefix ('sides.{0}.baseline' -f $Side) -Fields $RequiredStaticFitBaselineFields
    Add-MissingObjectProperties -Target $MissingStaticFitTemplateFields -Payload $StaticFitChecksPayload -Prefix ('sides.{0}.static_checks' -f $Side) -Fields $RequiredStaticFitCheckFields
    Add-MissingObjectProperties -Target $MissingStaticFitTemplateFields -Payload $StaticFitPostDoffPayload -Prefix ('sides.{0}.post_doff' -f $Side) -Fields $RequiredStaticFitPostDoffFields
    Add-MissingObjectProperties -Target $MissingStaticFitTemplateFields -Payload $StaticFitSymptomsPayload -Prefix ('sides.{0}.symptoms' -f $Side) -Fields $RequiredSafetyScreenFields
  }
  $Checks.Add((New-GateCheck -Id 'static_fit_input_template_required_fields' -Passed ($MissingStaticFitTemplateFields.Count -eq 0) -Evidence (($MissingStaticFitTemplateFields.ToArray() -join ', ')) -Reason 'Pilot static-fit template must keep every field required by the static-fit gate.')) | Out-Null

  $MovementTemplate = $null
  $MovementTemplateParsed = $false
  if (-not [string]::IsNullOrWhiteSpace($MovementTemplatePath) -and (Test-Path -LiteralPath $MovementTemplatePath -PathType Leaf)) {
    try {
      $MovementTemplate = Get-Content -LiteralPath $MovementTemplatePath -Raw | ConvertFrom-Json -ErrorAction Stop
      $MovementTemplateParsed = $true
    } catch {
      $MovementTemplateParsed = $false
    }
  }
  $Checks.Add((New-GateCheck -Id 'movement_input_template_parse' -Passed $MovementTemplateParsed -Evidence $MovementTemplatePath -Reason 'The pilot movement template must parse before package validation can trust its required field contract.')) | Out-Null
  $RequiredMovementTemplateContracts = @(
    'evidence_date',
    'placeholder_values',
    'pilot_identity_linkage',
    'record_linkage',
    'evidence_chronology',
    'test_duration',
    'required_pass_checks',
    'symptoms'
  )
  $MovementContractPayload = if ($MovementTemplateParsed) { $MovementTemplate.field_contract } else { $null }
  Add-MissingContractTextProperties -Target $MissingMovementTemplateContracts -Payload $MovementContractPayload -Fields $RequiredMovementTemplateContracts
  $Checks.Add((New-GateCheck -Id 'movement_input_template_contracts' -Passed ($MissingMovementTemplateContracts.Count -eq 0) -Evidence (($MissingMovementTemplateContracts.ToArray() -join ', ')) -Reason 'Pilot movement template must preserve all field contracts required by the movement gate.')) | Out-Null

  $RequiredMovementEvidenceFields = @(
    'date',
    'observer',
    'pilot_id',
    'prototype_revision',
    'pilot_static_fit_record_path',
    'test_duration_minutes'
  )
  $RequiredMovementPreconditionFields = @(
    'non_powered_only',
    'no_frame_or_power_coupling',
    'pilot_static_fit_gate_passed',
    'observer_present',
    'emergency_release_briefed',
    'stop_on_symptoms',
    'pilot_can_self_remove_or_abort'
  )
  $RequiredMovementCheckFields = @(
    'elbow_flexion_no_crease_compression',
    'elbow_extension_no_cuff_migration',
    'wrist_flexion_no_distal_edge_pressure',
    'wrist_extension_no_distal_edge_pressure',
    'wrist_lateral_no_strap_or_cable_interference',
    'hand_opening_full',
    'grip_formation_clear',
    'glove_removal_not_trapped',
    'wrist_assembly_removal_not_blocked',
    'outer_cable_route_no_snag',
    'quick_release_reachable_during_motion',
    'cuff_returns_to_safe_position_after_motion'
  )
  $RequiredPostMovementFields = @(
    'fingers_warm_after_motion',
    'normal_color_after_motion',
    'grip_strength_unchanged',
    'no_new_pressure_marks'
  )
  $MovementEvidencePayload = if ($MovementTemplateParsed) { $MovementTemplate.evidence } else { $null }
  $MovementPreconditionsPayload = if ($MovementTemplateParsed) { $MovementTemplate.preconditions } else { $null }
  $MovementSidesPayload = if ($MovementTemplateParsed) { $MovementTemplate.sides } else { $null }
  Add-MissingObjectProperties -Target $MissingMovementTemplateFields -Payload $MovementEvidencePayload -Prefix 'evidence' -Fields $RequiredMovementEvidenceFields
  Add-MissingObjectProperties -Target $MissingMovementTemplateFields -Payload $MovementPreconditionsPayload -Prefix 'preconditions' -Fields $RequiredMovementPreconditionFields
  foreach ($Side in @('left', 'right')) {
    $MovementSidePayload = $null
    if ($null -ne $MovementSidesPayload -and $null -ne $MovementSidesPayload.PSObject.Properties[$Side]) {
      $MovementSidePayload = $MovementSidesPayload.PSObject.Properties[$Side].Value
    }
    $MovementChecksPayload = if ($null -ne $MovementSidePayload) { $MovementSidePayload.movement_checks } else { $null }
    $PostMovementPayload = if ($null -ne $MovementSidePayload) { $MovementSidePayload.post_movement } else { $null }
    $MovementSymptomsPayload = if ($null -ne $MovementSidePayload) { $MovementSidePayload.symptoms } else { $null }
    Add-MissingObjectProperties -Target $MissingMovementTemplateFields -Payload $MovementChecksPayload -Prefix ('sides.{0}.movement_checks' -f $Side) -Fields $RequiredMovementCheckFields
    Add-MissingObjectProperties -Target $MissingMovementTemplateFields -Payload $PostMovementPayload -Prefix ('sides.{0}.post_movement' -f $Side) -Fields $RequiredPostMovementFields
    Add-MissingObjectProperties -Target $MissingMovementTemplateFields -Payload $MovementSymptomsPayload -Prefix ('sides.{0}.symptoms' -f $Side) -Fields $RequiredSafetyScreenFields
  }
  $Checks.Add((New-GateCheck -Id 'movement_input_template_required_fields' -Passed ($MissingMovementTemplateFields.Count -eq 0) -Evidence (($MissingMovementTemplateFields.ToArray() -join ', ')) -Reason 'Pilot movement template must keep every field required by the movement gate.')) | Out-Null

  $ReleaseCableTemplate = $null
  $ReleaseCableTemplateParsed = $false
  if (-not [string]::IsNullOrWhiteSpace($ReleaseCableTemplatePath) -and (Test-Path -LiteralPath $ReleaseCableTemplatePath -PathType Leaf)) {
    try {
      $ReleaseCableTemplate = Get-Content -LiteralPath $ReleaseCableTemplatePath -Raw | ConvertFrom-Json -ErrorAction Stop
      $ReleaseCableTemplateParsed = $true
    } catch {
      $ReleaseCableTemplateParsed = $false
    }
  }
  $Checks.Add((New-GateCheck -Id 'release_cable_input_template_parse' -Passed $ReleaseCableTemplateParsed -Evidence $ReleaseCableTemplatePath -Reason 'The quick-release/cable-snag template must parse before package validation can trust its required field contract.')) | Out-Null
  $RequiredReleaseCableTemplateContracts = @(
    'evidence_date',
    'placeholder_values',
    'pilot_identity_linkage',
    'record_linkage',
    'evidence_chronology',
    'test_duration',
    'required_pass_checks',
    'fail_observations'
  )
  $ReleaseCableContractPayload = if ($ReleaseCableTemplateParsed) { $ReleaseCableTemplate.field_contract } else { $null }
  Add-MissingContractTextProperties -Target $MissingReleaseCableTemplateContracts -Payload $ReleaseCableContractPayload -Fields $RequiredReleaseCableTemplateContracts
  $Checks.Add((New-GateCheck -Id 'release_cable_input_template_contracts' -Passed ($MissingReleaseCableTemplateContracts.Count -eq 0) -Evidence (($MissingReleaseCableTemplateContracts.ToArray() -join ', ')) -Reason 'Quick-release/cable-snag template must preserve all field contracts required by the release/cable gate.')) | Out-Null

  $RequiredReleaseCableEvidenceFields = @(
    'date',
    'observer',
    'pilot_id',
    'prototype_revision',
    'pilot_movement_record_path',
    'test_duration_minutes'
  )
  $RequiredReleaseCablePreconditionFields = @(
    'non_powered_only',
    'no_frame_or_power_coupling',
    'pilot_movement_gate_passed',
    'observer_present',
    'emergency_release_briefed',
    'stop_on_symptoms',
    'pilot_can_self_remove_or_abort'
  )
  $RequiredReleaseCheckFields = @(
    'bare_cuff_release_visible_tactile_reachable',
    'glove_base_mockup_release_visible_tactile_reachable',
    'wrist_assembly_mockup_release_visible_tactile_reachable',
    'forearm_frame_mockup_release_visible_tactile_reachable',
    'forearm_armor_mockup_release_visible_tactile_reachable',
    'populated_cable_sleeve_release_visible_tactile_reachable',
    'post_movement_release_visible_tactile_reachable',
    'opposite_hand_release_reachable',
    'same_side_reach_recorded',
    'release_loosens_upper_strap',
    'release_loosens_lower_strap',
    'cuff_removable_without_tools',
    'no_painful_wrist_posture_required',
    'glove_and_wrist_paths_not_trapped'
  )
  $RequiredCableSleeveFields = @(
    'outer_forearm_route_preserved',
    'no_inner_elbow_crossing',
    'no_wrist_bone_crossing',
    'no_palm_or_grip_crossing',
    'no_release_handle_obstruction',
    'no_snag_during_release',
    'no_snag_after_elbow_wrist_motion',
    'cable_not_trapped_after_release'
  )
  $RequiredReleaseFailObservationFields = @(
    'release_hidden',
    'release_not_found_by_touch',
    'release_blocked_by_glove_or_armor',
    'release_fails_to_loosen',
    'cuff_not_removable_without_tools',
    'painful_wrist_posture_required',
    'cable_trapped_after_release',
    'cable_crossed_no_go_zone'
  )
  $ReleaseCableEvidencePayload = if ($ReleaseCableTemplateParsed) { $ReleaseCableTemplate.evidence } else { $null }
  $ReleaseCablePreconditionsPayload = if ($ReleaseCableTemplateParsed) { $ReleaseCableTemplate.preconditions } else { $null }
  $ReleaseCableSidesPayload = if ($ReleaseCableTemplateParsed) { $ReleaseCableTemplate.sides } else { $null }
  Add-MissingObjectProperties -Target $MissingReleaseCableTemplateFields -Payload $ReleaseCableEvidencePayload -Prefix 'evidence' -Fields $RequiredReleaseCableEvidenceFields
  Add-MissingObjectProperties -Target $MissingReleaseCableTemplateFields -Payload $ReleaseCablePreconditionsPayload -Prefix 'preconditions' -Fields $RequiredReleaseCablePreconditionFields
  foreach ($Side in @('left', 'right')) {
    $ReleaseCableSidePayload = $null
    if ($null -ne $ReleaseCableSidesPayload -and $null -ne $ReleaseCableSidesPayload.PSObject.Properties[$Side]) {
      $ReleaseCableSidePayload = $ReleaseCableSidesPayload.PSObject.Properties[$Side].Value
    }
    $ReleaseChecksPayload = if ($null -ne $ReleaseCableSidePayload) { $ReleaseCableSidePayload.release_checks } else { $null }
    $CableSleevePayload = if ($null -ne $ReleaseCableSidePayload) { $ReleaseCableSidePayload.cable_sleeve_checks } else { $null }
    $ReleaseFailPayload = if ($null -ne $ReleaseCableSidePayload) { $ReleaseCableSidePayload.fail_observations } else { $null }
    Add-MissingObjectProperties -Target $MissingReleaseCableTemplateFields -Payload $ReleaseChecksPayload -Prefix ('sides.{0}.release_checks' -f $Side) -Fields $RequiredReleaseCheckFields
    Add-MissingObjectProperties -Target $MissingReleaseCableTemplateFields -Payload $CableSleevePayload -Prefix ('sides.{0}.cable_sleeve_checks' -f $Side) -Fields $RequiredCableSleeveFields
    Add-MissingObjectProperties -Target $MissingReleaseCableTemplateFields -Payload $ReleaseFailPayload -Prefix ('sides.{0}.fail_observations' -f $Side) -Fields $RequiredReleaseFailObservationFields
  }
  $Checks.Add((New-GateCheck -Id 'release_cable_input_template_required_fields' -Passed ($MissingReleaseCableTemplateFields.Count -eq 0) -Evidence (($MissingReleaseCableTemplateFields.ToArray() -join ', ')) -Reason 'Quick-release/cable-snag template must keep every field required by the release/cable gate.')) | Out-Null

  $EngineeringTemplate = $null
  $EngineeringTemplateParsed = $false
  if (-not [string]::IsNullOrWhiteSpace($EngineeringTemplatePath) -and (Test-Path -LiteralPath $EngineeringTemplatePath -PathType Leaf)) {
    try {
      $EngineeringTemplate = Get-Content -LiteralPath $EngineeringTemplatePath -Raw | ConvertFrom-Json -ErrorAction Stop
      $EngineeringTemplateParsed = $true
    } catch {
      $EngineeringTemplateParsed = $false
    }
  }
  $Checks.Add((New-GateCheck -Id 'engineering_input_template_parse' -Passed $EngineeringTemplateParsed -Evidence $EngineeringTemplatePath -Reason 'The engineering-review template must parse before package validation can trust its required field contract.')) | Out-Null
  $RequiredEngineeringTemplateContracts = @(
    'evidence_date',
    'placeholder_values',
    'pilot_identity_linkage',
    'evidence_chronology',
    'required_pass_checks',
    'required_false_checks',
    'record_linkage',
    'review_scope'
  )
  $EngineeringContractPayload = if ($EngineeringTemplateParsed) { $EngineeringTemplate.field_contract } else { $null }
  Add-MissingContractTextProperties -Target $MissingEngineeringTemplateContracts -Payload $EngineeringContractPayload -Fields $RequiredEngineeringTemplateContracts
  $Checks.Add((New-GateCheck -Id 'engineering_input_template_contracts' -Passed ($MissingEngineeringTemplateContracts.Count -eq 0) -Evidence (($MissingEngineeringTemplateContracts.ToArray() -join ', ')) -Reason 'Engineering-review template must preserve all field contracts required by the engineering gate.')) | Out-Null

  $RequiredEngineeringEvidenceFields = @(
    'date',
    'reviewer',
    'reviewer_role',
    'reviewer_credential_reference',
    'pilot_id',
    'quick_release_cable_snag_record_path',
    'review_scope'
  )
  $RequiredReviewConstraintFields = @(
    'documentation_package_reviewed',
    'measurement_record_reviewed',
    'mockup_record_reviewed',
    'mannequin_record_reviewed',
    'pilot_static_record_reviewed',
    'pilot_movement_record_reviewed',
    'quick_release_cable_record_reviewed',
    'no_load_bearing_claim_approved',
    'no_powered_testing_cleared',
    'no_frame_coupled_testing_cleared',
    'fr018_implementation_not_cleared',
    'redesign_items_closed_or_blocked'
  )
  $RequiredSafetyReviewFields = @(
    'circulation_nerve_risk_reviewed',
    'quick_release_access_reviewed',
    'glove_wrist_removal_reviewed',
    'cable_route_reviewed',
    'symptom_fail_conditions_reviewed',
    'stop_conditions_preserved'
  )
  $RequiredReviewDecisionFields = @(
    'non_powered_fr017_physical_validation_accepted',
    'requires_redesign',
    'load_bearing_use_approved',
    'powered_testing_approved',
    'frame_coupled_testing_approved',
    'fr018_implementation_cleared',
    'engineering_review_notes'
  )
  $EngineeringEvidencePayload = if ($EngineeringTemplateParsed) { $EngineeringTemplate.evidence } else { $null }
  $ReviewConstraintsPayload = if ($EngineeringTemplateParsed) { $EngineeringTemplate.review_constraints } else { $null }
  $SafetyReviewPayload = if ($EngineeringTemplateParsed) { $EngineeringTemplate.safety_review } else { $null }
  $ReviewDecisionPayload = if ($EngineeringTemplateParsed) { $EngineeringTemplate.review_decision } else { $null }
  Add-MissingObjectProperties -Target $MissingEngineeringTemplateFields -Payload $EngineeringEvidencePayload -Prefix 'evidence' -Fields $RequiredEngineeringEvidenceFields
  Add-MissingObjectProperties -Target $MissingEngineeringTemplateFields -Payload $ReviewConstraintsPayload -Prefix 'review_constraints' -Fields $RequiredReviewConstraintFields
  Add-MissingObjectProperties -Target $MissingEngineeringTemplateFields -Payload $SafetyReviewPayload -Prefix 'safety_review' -Fields $RequiredSafetyReviewFields
  Add-MissingObjectProperties -Target $MissingEngineeringTemplateFields -Payload $ReviewDecisionPayload -Prefix 'review_decision' -Fields $RequiredReviewDecisionFields
  $Checks.Add((New-GateCheck -Id 'engineering_input_template_required_fields' -Passed ($MissingEngineeringTemplateFields.Count -eq 0) -Evidence (($MissingEngineeringTemplateFields.ToArray() -join ', ')) -Reason 'Engineering-review template must keep every field required by the engineering gate.')) | Out-Null

  $FinalDecisionTemplate = $null
  $FinalDecisionTemplateParsed = $false
  if (-not [string]::IsNullOrWhiteSpace($FinalDecisionTemplatePath) -and (Test-Path -LiteralPath $FinalDecisionTemplatePath -PathType Leaf)) {
    try {
      $FinalDecisionTemplate = Get-Content -LiteralPath $FinalDecisionTemplatePath -Raw | ConvertFrom-Json -ErrorAction Stop
      $FinalDecisionTemplateParsed = $true
    } catch {
      $FinalDecisionTemplateParsed = $false
    }
  }
  $Checks.Add((New-GateCheck -Id 'final_decision_input_template_parse' -Passed $FinalDecisionTemplateParsed -Evidence $FinalDecisionTemplatePath -Reason 'The human final decision template must parse before package validation can trust its required field contract.')) | Out-Null
  $RequiredFinalDecisionTemplateContracts = @(
    'date',
    'decision_reviewer',
    'final_physical_gate_status',
    'final_physical_gate_record_path',
    'decision_locks',
    'stage17_completion_claim_requested',
    'physical_validation_accepted_by_human_reviewer',
    'completion_ledger_update_required',
    'completion_decision_notes'
  )
  $FinalDecisionContractPayload = if ($FinalDecisionTemplateParsed) { $FinalDecisionTemplate.field_contract } else { $null }
  Add-MissingContractTextProperties -Target $MissingFinalDecisionTemplateContracts -Payload $FinalDecisionContractPayload -Fields $RequiredFinalDecisionTemplateContracts
  $Checks.Add((New-GateCheck -Id 'final_decision_input_template_contracts' -Passed ($MissingFinalDecisionTemplateContracts.Count -eq 0) -Evidence (($MissingFinalDecisionTemplateContracts.ToArray() -join ', ')) -Reason 'Human final decision template must preserve all field contracts required by the final physical completion-decision handoff.')) | Out-Null

  $RequiredFinalDecisionEvidenceFields = @(
    'date',
    'decision_reviewer',
    'reviewer_role',
    'pilot_id',
    'final_physical_gate_status',
    'final_physical_gate_record_path'
  )
  $RequiredFinalDecisionLockFields = @(
    'real_records_reviewed',
    'all_stop_conditions_reviewed',
    'no_unresolved_safety_fail_conditions',
    'no_powered_testing_cleared',
    'no_frame_coupled_testing_cleared',
    'no_load_bearing_use_approved',
    'fr018_implementation_not_cleared'
  )
  $RequiredCompletionDecisionFields = @(
    'stage17_completion_claim_requested',
    'physical_validation_accepted_by_human_reviewer',
    'completion_ledger_update_required',
    'completion_decision_notes'
  )
  $RequiredFinalDecisionNoFakeLockFields = @(
    'template_is_not_physical_validation',
    'requires_real_records',
    'fr018_implementation_cleared',
    'powered_or_frame_coupled_testing_cleared'
  )
  $FinalDecisionEvidencePayload = if ($FinalDecisionTemplateParsed) { $FinalDecisionTemplate.evidence } else { $null }
  $FinalDecisionLocksPayload = if ($FinalDecisionTemplateParsed) { $FinalDecisionTemplate.decision_locks } else { $null }
  $CompletionDecisionPayload = if ($FinalDecisionTemplateParsed) { $FinalDecisionTemplate.completion_decision } else { $null }
  $FinalDecisionNoFakeLockPayload = if ($FinalDecisionTemplateParsed) { $FinalDecisionTemplate.no_fake_validation_lock } else { $null }
  Add-MissingObjectProperties -Target $MissingFinalDecisionTemplateFields -Payload $FinalDecisionEvidencePayload -Prefix 'evidence' -Fields $RequiredFinalDecisionEvidenceFields
  Add-MissingObjectProperties -Target $MissingFinalDecisionTemplateFields -Payload $FinalDecisionLocksPayload -Prefix 'decision_locks' -Fields $RequiredFinalDecisionLockFields
  Add-MissingObjectProperties -Target $MissingFinalDecisionTemplateFields -Payload $CompletionDecisionPayload -Prefix 'completion_decision' -Fields $RequiredCompletionDecisionFields
  Add-MissingObjectProperties -Target $MissingFinalDecisionTemplateFields -Payload $FinalDecisionNoFakeLockPayload -Prefix 'no_fake_validation_lock' -Fields $RequiredFinalDecisionNoFakeLockFields
  $Checks.Add((New-GateCheck -Id 'final_decision_input_template_required_fields' -Passed ($MissingFinalDecisionTemplateFields.Count -eq 0) -Evidence (($MissingFinalDecisionTemplateFields.ToArray() -join ', ')) -Reason 'Human final decision template must keep every field required by the final physical completion-decision handoff.')) | Out-Null

  $RequiredBlockedInputs = @(
    'left_right_forearm_measurements',
    'safety_critical_landmark_confirmation',
    'soft_cuff_prototype_or_mockup',
    'mannequin_or_arm_form',
    'future_interface_mock_geometry',
    'cable_sleeve_mock',
    'pilot_static_fit_session',
    'pilot_movement_session',
    'quick_release_test_session',
    'professional_engineering_review',
    'human_final_stage17_completion_decision'
  )
  $MissingBlockedInputs = @($RequiredBlockedInputs | Where-Object { $BlockedInputs -notcontains $_ })
  $Checks.Add((New-GateCheck -Id 'blocked_inputs_preserved' -Passed ($MissingBlockedInputs.Count -eq 0) -Evidence (($MissingBlockedInputs -join ', ')))) | Out-Null

  $RequiredSafetyConditions = @(
    'numbness',
    'tingling',
    'cold_fingers',
    'discoloration',
    'hand_weakness',
    'wrist_pain',
    'sharp_pressure',
    'reduced_finger_motion',
    'loss_of_grip_strength',
    'unconfirmed_landmark_boundaries',
    'unreachable_release'
  )
  $MissingSafetyConditions = @($RequiredSafetyConditions | Where-Object { $SafetyFailConditions -notcontains $_ })
  $Checks.Add((New-GateCheck -Id 'safety_fail_conditions_preserved' -Passed ($MissingSafetyConditions.Count -eq 0) -Evidence (($MissingSafetyConditions -join ', ')))) | Out-Null
}

foreach ($GateScript in $RequiredGateScripts) {
  $GateScriptPath = Join-Path $ResolvedGateScriptRoot $GateScript
  if (-not (Test-Path -LiteralPath $GateScriptPath -PathType Leaf)) {
    $MissingGateScripts.Add($GateScript) | Out-Null
    continue
  }

  $ParseErrors = $null
  $ParseTokens = $null
  [System.Management.Automation.Language.Parser]::ParseFile($GateScriptPath, [ref]$ParseTokens, [ref]$ParseErrors) | Out-Null
  if ($ParseErrors.Count -gt 0) {
    $InvalidGateScripts.Add($GateScript) | Out-Null
  }
}
$Checks.Add((New-GateCheck -Id 'required_gate_scripts_exist' -Passed ($MissingGateScripts.Count -eq 0) -Evidence (($MissingGateScripts.ToArray() -join ', ')) -Reason 'Every FR-017 validation-chain gate script must exist before the package can be treated as structurally complete.')) | Out-Null
$Checks.Add((New-GateCheck -Id 'required_gate_scripts_parse' -Passed ($InvalidGateScripts.Count -eq 0) -Evidence (($InvalidGateScripts.ToArray() -join ', ')) -Reason 'Every FR-017 validation-chain gate script must parse before the package can be treated as structurally complete.')) | Out-Null

$FailedChecks = @($Checks.ToArray() | Where-Object { -not [bool]$_.passed })
$StructuralGatePassed = $ManifestExists -and $null -ne $Manifest -and $FailedChecks.Count -eq 0
$Status = if ($StructuralGatePassed) { 'blocked_physical_validation' } else { 'failed_contract' }
$ExitCode = if ($StructuralGatePassed) { 0 } else { 1 }

$Payload = [ordered]@{
  kind = 'francis.fr017.stage17.validation_gate'
  mode = $Mode
  status = $Status
  documentation_complete = $StructuralGatePassed
  evidence_containers_complete = $StructuralGatePassed
  physical_validation_complete = $false
  physical_validation_status = if ([string]::IsNullOrWhiteSpace($PhysicalValidation)) { 'unknown' } else { $PhysicalValidation }
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  fr018_status = if ([string]::IsNullOrWhiteSpace($Fr018Status)) { 'unknown' } else { $Fr018Status }
  read_only_contract = $true
  writes_repo = $false
  writes_data = $false
  grants_execution_authority = $false
  grants_mutation_authority = $false
  manifest_path = $ResolvedManifestPath
  gate_script_root = $ResolvedGateScriptRoot
  record_count = $RecordCount
  custom_record_count = $CustomRecordCount
  required_gate_scripts = @($RequiredGateScripts)
  missing_gate_scripts = @($MissingGateScripts.ToArray())
  invalid_gate_scripts = @($InvalidGateScripts.ToArray())
  blocked_inputs = $BlockedInputs
  safety_fail_conditions = $SafetyFailConditions
  missing_measurement_template_contracts = @($MissingMeasurementTemplateContracts.ToArray())
  missing_measurement_template_fields = @($MissingMeasurementTemplateFields.ToArray())
  missing_mockup_template_contracts = @($MissingMockupTemplateContracts.ToArray())
  missing_mockup_template_fields = @($MissingMockupTemplateFields.ToArray())
  missing_mannequin_template_contracts = @($MissingMannequinTemplateContracts.ToArray())
  missing_mannequin_template_fields = @($MissingMannequinTemplateFields.ToArray())
  missing_static_fit_template_contracts = @($MissingStaticFitTemplateContracts.ToArray())
  missing_static_fit_template_fields = @($MissingStaticFitTemplateFields.ToArray())
  missing_movement_template_contracts = @($MissingMovementTemplateContracts.ToArray())
  missing_movement_template_fields = @($MissingMovementTemplateFields.ToArray())
  missing_release_cable_template_contracts = @($MissingReleaseCableTemplateContracts.ToArray())
  missing_release_cable_template_fields = @($MissingReleaseCableTemplateFields.ToArray())
  missing_engineering_template_contracts = @($MissingEngineeringTemplateContracts.ToArray())
  missing_engineering_template_fields = @($MissingEngineeringTemplateFields.ToArray())
  missing_final_decision_template_contracts = @($MissingFinalDecisionTemplateContracts.ToArray())
  missing_final_decision_template_fields = @($MissingFinalDecisionTemplateFields.ToArray())
  failed_checks = @($FailedChecks | ForEach-Object { [string]$_.id })
  checks = @($Checks.ToArray())
  next_actions = @(
    'confirm_safety_critical_landmarks_before_measurement_use',
    'enter_left_right_forearm_measurements',
    'build_non_powered_soft_cuff_mockup',
    'run_mannequin_interface_test',
    'run_pilot_static_fit_test',
    'run_pilot_movement_test',
    'run_quick_release_and_cable_snag_tests',
    'obtain_professional_engineering_review_before_load_or_powered_use',
    'complete_human_final_stage17_completion_decision_record_after_final_physical_gate_readiness'
  )
}

$Payload | ConvertTo-Json -Depth 8
exit $ExitCode
