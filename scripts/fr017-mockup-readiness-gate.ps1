[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$MeasurementPath = '',

  [string]$MockupPath = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$MeasurementIntakeGateScript = Join-Path $PSScriptRoot 'fr017-measurement-intake.ps1'

function Resolve-ReadinessPath {
  param([string]$Path)

  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Path))
}

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

function Test-MissingOrPendingText {
  param([object]$Value)

  if ($null -eq $Value) {
    return $true
  }
  $Text = ([string]$Value).Trim()
  return [string]::IsNullOrWhiteSpace($Text) -or [string]::Equals($Text, 'PENDING', [System.StringComparison]::OrdinalIgnoreCase)
}

function Add-UniqueStrings {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [object]$Values
  )

  foreach ($Value in (ConvertTo-StringArray -Value $Values)) {
    if (-not $Target.Contains($Value)) {
      $Target.Add($Value) | Out-Null
    }
  }
}

function Test-PositiveNumber {
  param([object]$Value)

  if ($null -eq $Value) {
    return $false
  }
  $Number = 0.0
  if (-not [double]::TryParse([string]$Value, [ref]$Number)) {
    return $false
  }
  return $Number -gt 0
}

function Add-IfMissingText {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [string]$Field,
    [object]$Value
  )

  if (Test-MissingOrPendingText -Value $Value) {
    $Target.Add($Field) | Out-Null
  }
}

function Add-EvidenceDateCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [string]$Field,
    [object]$Value
  )

  if (Test-MissingOrPendingText -Value $Value) {
    $Missing.Add($Field) | Out-Null
    return
  }

  $Text = ([string]$Value).Trim()
  $ParsedDate = [datetime]::MinValue
  $ParseOk = [datetime]::TryParseExact(
    $Text,
    'yyyy-MM-dd',
    [System.Globalization.CultureInfo]::InvariantCulture,
    [System.Globalization.DateTimeStyles]::None,
    [ref]$ParsedDate
  )
  if (-not $ParseOk) {
    $Invalid.Add($Field) | Out-Null
    return
  }

  if ($ParsedDate.Date -gt [datetime]::Today) {
    $Invalid.Add($Field) | Out-Null
  }
}

function Get-EvidenceDateOrNull {
  param([object]$Payload)

  $Evidence = Get-PropertyValue -Payload $Payload -Name 'evidence'
  $Value = Get-PropertyValue -Payload $Evidence -Name 'date'
  if (Test-MissingOrPendingText -Value $Value) {
    return $null
  }

  $Text = ([string]$Value).Trim()
  $ParsedDate = [datetime]::MinValue
  $ParseOk = [datetime]::TryParseExact(
    $Text,
    'yyyy-MM-dd',
    [System.Globalization.CultureInfo]::InvariantCulture,
    [System.Globalization.DateTimeStyles]::None,
    [ref]$ParsedDate
  )
  if (-not $ParseOk) {
    return $null
  }

  return $ParsedDate.Date
}

function Add-MockupBuildMethodCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [string]$Field,
    [object]$Value
  )

  if (Test-MissingOrPendingText -Value $Value) {
    $Missing.Add($Field) | Out-Null
    return
  }

  $Text = ([string]$Value).Trim()
  if ($Text.IndexOf('non-powered', [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
    $Invalid.Add($Field) | Out-Null
    return
  }

  foreach ($Fragment in @('soft', 'semi-rigid', 'semi rigid')) {
    if ($Text.IndexOf($Fragment, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
      return
    }
  }

  $Invalid.Add($Field) | Out-Null
}

function Add-IfMissingPositiveNumber {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [string]$Field,
    [object]$Value
  )

  if (-not (Test-PositiveNumber -Value $Value)) {
    $Target.Add($Field) | Out-Null
  }
}

function Get-BoolState {
  param([object]$Value)

  if ($null -eq $Value) {
    return 'missing'
  }
  if ($Value -is [bool]) {
    if ($Value) {
      return 'true'
    }
    return 'false'
  }

  if (Test-MissingOrPendingText -Value $Value) {
    return 'missing'
  }
  return 'invalid'
}

function Add-RequiredTrueCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [System.Collections.Generic.List[string]]$Redesign,
    [string]$Field,
    [object]$Value
  )

  $State = Get-BoolState -Value $Value
  if ($State -eq 'missing') {
    $Missing.Add($Field) | Out-Null
  } elseif ($State -eq 'invalid') {
    $Invalid.Add($Field) | Out-Null
  } elseif ($State -eq 'false') {
    $Redesign.Add($Field) | Out-Null
  }
}

function Test-PresentText {
  param([object]$Value)

  return -not (Test-MissingOrPendingText -Value $Value)
}

function Invoke-MeasurementIntakeGate {
  param([string]$ResolvedMeasurementPath)

  $PowerShellExe = (Get-Process -Id $PID).Path
  $RawOutput = & $PowerShellExe -NoProfile -ExecutionPolicy Bypass -File $MeasurementIntakeGateScript -Mode Status -MeasurementPath $ResolvedMeasurementPath
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

$SafetyScreenFields = @(
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

$RequiredMaterialFields = @(
  'padding_layer',
  'semi_rigid_outer_layer',
  'upper_forearm_strap',
  'lower_forearm_strap',
  'quick_release',
  'outer_forearm_cable_sleeve',
  'non_load_bearing_alignment_tabs',
  'sensor_placeholder_blanks'
)

$RequiredConstraintFields = @(
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

$RequiredSideCheckFields = @(
  'upper_strap_width_matches_measurement',
  'lower_strap_width_matches_measurement',
  'bone_relief_channel_present',
  'inner_forearm_no_pressure_zone_marked',
  'wrist_clearance_kept',
  'quick_release_installed_outer_or_lateral',
  'alignment_tabs_non_load_bearing',
  'cable_sleeve_outer_route_only'
)

$DefaultMeasurementPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MEASUREMENTS-INPUT-TEMPLATE.json'
$DefaultMockupPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json'
$ResolvedMeasurementPath = if ([string]::IsNullOrWhiteSpace($MeasurementPath)) { $DefaultMeasurementPath } else { Resolve-ReadinessPath -Path $MeasurementPath }
$ResolvedMockupPath = if ([string]::IsNullOrWhiteSpace($MockupPath)) { $DefaultMockupPath } else { Resolve-ReadinessPath -Path $MockupPath }
$UsingMeasurementTemplate = [string]::IsNullOrWhiteSpace($MeasurementPath)
$UsingMockupTemplate = [string]::IsNullOrWhiteSpace($MockupPath)

$MeasurementMissing = New-Object System.Collections.Generic.List[string]
$MeasurementInvalid = New-Object System.Collections.Generic.List[string]
$MeasurementConsistencyViolations = New-Object System.Collections.Generic.List[string]
$MarkedZoneSpecificityViolations = New-Object System.Collections.Generic.List[string]
$RepeatabilityBlockers = New-Object System.Collections.Generic.List[string]
$LeftRightIndependenceBlockers = New-Object System.Collections.Generic.List[string]
$MeasurementConditionBlockers = New-Object System.Collections.Generic.List[string]
$LandmarkConfirmationBlockers = New-Object System.Collections.Generic.List[string]
$MeasurementNoteBlockers = New-Object System.Collections.Generic.List[string]
$SafetyBlockers = New-Object System.Collections.Generic.List[string]
$MockupMissing = New-Object System.Collections.Generic.List[string]
$MockupInvalid = New-Object System.Collections.Generic.List[string]
$MockupRedesign = New-Object System.Collections.Generic.List[string]
$MockupLinkageViolations = New-Object System.Collections.Generic.List[string]
$MockupChronologyViolations = New-Object System.Collections.Generic.List[string]

$MeasurementParseOk = $false
$MockupParseOk = $false
$MeasurementStatus = 'pending_measurement_intake'
$MockupStatus = 'pending_mockup_build_record'
$Status = 'pending_measurement_intake'
$ExitCode = 0
$MeasurementIntake = Invoke-MeasurementIntakeGate -ResolvedMeasurementPath $ResolvedMeasurementPath
$MeasurementIntakeStatus = if ([bool]$MeasurementIntake.parse_ok) { [string]$MeasurementIntake.payload.status } else { 'failed_measurement_intake_gate_parse' }
$MeasurementIntakeReady = [bool]$MeasurementIntake.parse_ok -and [int]$MeasurementIntake.exit_code -eq 0 -and $MeasurementIntakeStatus -eq 'ready_for_non_powered_mockup_patterning'
$MeasurementIntakeFailed = (-not [bool]$MeasurementIntake.parse_ok) -or [int]$MeasurementIntake.exit_code -ne 0 -or $MeasurementIntakeStatus.StartsWith('failed_') -or $MeasurementIntakeStatus.StartsWith('missing_') -or $MeasurementIntakeStatus.StartsWith('invalid_')

if (-not (Test-Path -LiteralPath $ResolvedMeasurementPath -PathType Leaf)) {
  $MeasurementStatus = 'failed_measurement_record'
  $MeasurementInvalid.Add('measurement_file') | Out-Null
} else {
  try {
    $MeasurementPayload = Get-Content -LiteralPath $ResolvedMeasurementPath -Raw | ConvertFrom-Json -ErrorAction Stop
    $MeasurementParseOk = $true
  } catch {
    $MeasurementStatus = 'failed_measurement_record'
    $MeasurementInvalid.Add('measurement_json_parse') | Out-Null
  }
}

if ($MeasurementParseOk) {
  if ([string](Get-PropertyValue -Payload $MeasurementPayload -Name 'kind' -Default '') -ne 'francis.fr017.measurements.v1') {
    $MeasurementInvalid.Add('kind') | Out-Null
  }
  if ([string](Get-PropertyValue -Payload $MeasurementPayload -Name 'component' -Default '') -ne 'FR-017 Forearm Cuffs') {
    $MeasurementInvalid.Add('component') | Out-Null
  }
  if ([string](Get-PropertyValue -Payload $MeasurementPayload -Name 'units' -Default '') -ne 'mm') {
    $MeasurementInvalid.Add('units') | Out-Null
  }

  $Evidence = Get-PropertyValue -Payload $MeasurementPayload -Name 'evidence'
  Add-EvidenceDateCheck -Missing $MeasurementMissing -Invalid $MeasurementInvalid -Field 'evidence.date' -Value (Get-PropertyValue -Payload $Evidence -Name 'date')
  Add-IfMissingText -Target $MeasurementMissing -Field 'evidence.observer' -Value (Get-PropertyValue -Payload $Evidence -Name 'observer')
  Add-IfMissingText -Target $MeasurementMissing -Field 'evidence.method' -Value (Get-PropertyValue -Payload $Evidence -Name 'method')
  Add-IfMissingText -Target $MeasurementMissing -Field 'evidence.posture' -Value (Get-PropertyValue -Payload $Evidence -Name 'posture')

  $Sides = Get-PropertyValue -Payload $MeasurementPayload -Name 'sides'
  $MarkedZones = Get-PropertyValue -Payload $MeasurementPayload -Name 'marked_zones'
  foreach ($Side in @('left', 'right')) {
    $SideMeasurements = Get-PropertyValue -Payload $Sides -Name $Side
    foreach ($Field in $RequiredMeasurementFields) {
      Add-IfMissingPositiveNumber -Target $MeasurementMissing -Field ('sides.{0}.{1}' -f $Side, $Field) -Value (Get-PropertyValue -Payload $SideMeasurements -Name $Field)
    }

    $SideZones = Get-PropertyValue -Payload $MarkedZones -Name $Side
    foreach ($Field in $RequiredMarkedZoneFields) {
      Add-IfMissingText -Target $MeasurementMissing -Field ('marked_zones.{0}.{1}' -f $Side, $Field) -Value (Get-PropertyValue -Payload $SideZones -Name $Field)
    }
  }

  $SafetyScreen = Get-PropertyValue -Payload $MeasurementPayload -Name 'safety_screen'
  foreach ($Field in $SafetyScreenFields) {
    $State = Get-BoolState -Value (Get-PropertyValue -Payload $SafetyScreen -Name $Field)
    if ($State -eq 'missing') {
      $MeasurementMissing.Add('safety_screen.' + $Field) | Out-Null
    } elseif ($State -eq 'invalid') {
      $MeasurementInvalid.Add('safety_screen.' + $Field) | Out-Null
    } elseif ($State -eq 'true') {
      $SafetyBlockers.Add($Field) | Out-Null
    }
  }

  if ($MeasurementInvalid.Count -gt 0) {
    $MeasurementStatus = 'failed_measurement_record'
  } elseif ($MeasurementMissing.Count -gt 0 -or $UsingMeasurementTemplate) {
    $MeasurementStatus = 'pending_measurement_intake'
  } elseif ($SafetyBlockers.Count -gt 0) {
    $MeasurementStatus = 'failed_requires_redesign_or_medical_review'
  } else {
    $MeasurementStatus = 'ready_for_non_powered_mockup_patterning'
  }
}

if ([bool]$MeasurementIntake.parse_ok) {
  Add-UniqueStrings -Target $MeasurementMissing -Values (Get-PropertyValue -Payload $MeasurementIntake.payload -Name 'missing_fields')
  Add-UniqueStrings -Target $MeasurementInvalid -Values (Get-PropertyValue -Payload $MeasurementIntake.payload -Name 'invalid_fields')
  Add-UniqueStrings -Target $MeasurementConsistencyViolations -Values (Get-PropertyValue -Payload $MeasurementIntake.payload -Name 'measurement_consistency_violations')
  Add-UniqueStrings -Target $MarkedZoneSpecificityViolations -Values (Get-PropertyValue -Payload $MeasurementIntake.payload -Name 'marked_zone_specificity_violations')
  Add-UniqueStrings -Target $RepeatabilityBlockers -Values (Get-PropertyValue -Payload $MeasurementIntake.payload -Name 'repeatability_blockers')
  Add-UniqueStrings -Target $LeftRightIndependenceBlockers -Values (Get-PropertyValue -Payload $MeasurementIntake.payload -Name 'left_right_independence_blockers')
  Add-UniqueStrings -Target $MeasurementConditionBlockers -Values (Get-PropertyValue -Payload $MeasurementIntake.payload -Name 'measurement_condition_blockers')
  Add-UniqueStrings -Target $LandmarkConfirmationBlockers -Values (Get-PropertyValue -Payload $MeasurementIntake.payload -Name 'landmark_confirmation_blockers')
  Add-UniqueStrings -Target $MeasurementNoteBlockers -Values (Get-PropertyValue -Payload $MeasurementIntake.payload -Name 'measurement_note_blockers')
  Add-UniqueStrings -Target $SafetyBlockers -Values (Get-PropertyValue -Payload $MeasurementIntake.payload -Name 'safety_blockers')
} else {
  Add-UniqueStrings -Target $MeasurementInvalid -Values 'measurement_intake_gate_parse'
}

if (-not $MeasurementIntakeReady) {
  if ($MeasurementIntakeStatus -eq 'pending_measurements') {
    $MeasurementStatus = 'pending_measurement_intake'
  } elseif ($MeasurementIntakeFailed) {
    $MeasurementStatus = $MeasurementIntakeStatus
  }
}

if ($MeasurementStatus -eq 'ready_for_non_powered_mockup_patterning') {
  if (-not (Test-Path -LiteralPath $ResolvedMockupPath -PathType Leaf)) {
    $MockupStatus = 'failed_mockup_record'
    $MockupInvalid.Add('mockup_file') | Out-Null
  } else {
    try {
      $MockupPayload = Get-Content -LiteralPath $ResolvedMockupPath -Raw | ConvertFrom-Json -ErrorAction Stop
      $MockupParseOk = $true
    } catch {
      $MockupStatus = 'failed_mockup_record'
      $MockupInvalid.Add('mockup_json_parse') | Out-Null
    }
  }

  if ($MockupParseOk) {
    if ([string](Get-PropertyValue -Payload $MockupPayload -Name 'kind' -Default '') -ne 'francis.fr017.mockup_build.v1') {
      $MockupInvalid.Add('kind') | Out-Null
    }
    if ([string](Get-PropertyValue -Payload $MockupPayload -Name 'component' -Default '') -ne 'FR-017 Forearm Cuffs') {
      $MockupInvalid.Add('component') | Out-Null
    }

    $MockupEvidence = Get-PropertyValue -Payload $MockupPayload -Name 'evidence'
    Add-EvidenceDateCheck -Missing $MockupMissing -Invalid $MockupInvalid -Field 'evidence.date' -Value (Get-PropertyValue -Payload $MockupEvidence -Name 'date')
    Add-IfMissingText -Target $MockupMissing -Field 'evidence.observer' -Value (Get-PropertyValue -Payload $MockupEvidence -Name 'observer')
    Add-MockupBuildMethodCheck -Missing $MockupMissing -Invalid $MockupInvalid -Field 'evidence.build_method' -Value (Get-PropertyValue -Payload $MockupEvidence -Name 'build_method')
    $MockupMeasurementRecordPath = Get-PropertyValue -Payload $MockupEvidence -Name 'measurement_record_path'
    Add-IfMissingText -Target $MockupMissing -Field 'evidence.measurement_record_path' -Value $MockupMeasurementRecordPath
    if (Test-PresentText -Value $MockupMeasurementRecordPath) {
      try {
        $ResolvedMockupMeasurementPath = Resolve-ReadinessPath -Path ([string]$MockupMeasurementRecordPath)
        if (-not [string]::Equals($ResolvedMockupMeasurementPath, $ResolvedMeasurementPath, [System.StringComparison]::OrdinalIgnoreCase)) {
          $MockupLinkageViolations.Add('evidence.measurement_record_path_must_match_measurement_path') | Out-Null
        }
      } catch {
        $MockupInvalid.Add('evidence.measurement_record_path') | Out-Null
      }
    }

    $MeasurementEvidenceDate = Get-EvidenceDateOrNull -Payload $MeasurementPayload
    $MockupEvidenceDate = Get-EvidenceDateOrNull -Payload $MockupPayload
    if ($null -ne $MeasurementEvidenceDate -and $null -ne $MockupEvidenceDate -and $MockupEvidenceDate -lt $MeasurementEvidenceDate) {
      $MockupChronologyViolations.Add('evidence.date_before_measurement.evidence.date') | Out-Null
    }

    $Materials = Get-PropertyValue -Payload $MockupPayload -Name 'materials'
    foreach ($Field in $RequiredMaterialFields) {
      Add-IfMissingText -Target $MockupMissing -Field ('materials.{0}' -f $Field) -Value (Get-PropertyValue -Payload $Materials -Name $Field)
    }

    $Constraints = Get-PropertyValue -Payload $MockupPayload -Name 'constraints'
    foreach ($Field in $RequiredConstraintFields) {
      Add-RequiredTrueCheck -Missing $MockupMissing -Invalid $MockupInvalid -Redesign $MockupRedesign -Field ('constraints.{0}' -f $Field) -Value (Get-PropertyValue -Payload $Constraints -Name $Field)
    }

    $MockupSides = Get-PropertyValue -Payload $MockupPayload -Name 'sides'
    foreach ($Side in @('left', 'right')) {
      $SideChecks = Get-PropertyValue -Payload $MockupSides -Name $Side
      foreach ($Field in $RequiredSideCheckFields) {
        Add-RequiredTrueCheck -Missing $MockupMissing -Invalid $MockupInvalid -Redesign $MockupRedesign -Field ('sides.{0}.{1}' -f $Side, $Field) -Value (Get-PropertyValue -Payload $SideChecks -Name $Field)
      }
    }

    if ($MockupInvalid.Count -gt 0 -or $MockupLinkageViolations.Count -gt 0 -or $MockupChronologyViolations.Count -gt 0) {
      $MockupStatus = 'failed_mockup_record'
    } elseif ($MockupMissing.Count -gt 0 -or $UsingMockupTemplate) {
      $MockupStatus = 'pending_mockup_build_record'
    } elseif ($MockupRedesign.Count -gt 0) {
      $MockupStatus = 'failed_requires_mockup_redesign'
    } else {
      $MockupStatus = 'ready_for_mannequin_interface_test'
    }
  }
}

if ($MeasurementStatus.StartsWith('failed_') -or $MeasurementStatus.StartsWith('missing_') -or $MeasurementStatus.StartsWith('invalid_')) {
  $Status = $MeasurementStatus
  $ExitCode = 1
} elseif ($MeasurementStatus -ne 'ready_for_non_powered_mockup_patterning') {
  $Status = 'pending_measurement_intake'
} elseif ($MockupStatus -eq 'failed_mockup_record' -or $MockupStatus -eq 'failed_requires_mockup_redesign') {
  $Status = $MockupStatus
  $ExitCode = 1
} elseif ($MockupStatus -eq 'ready_for_mannequin_interface_test') {
  $Status = 'ready_for_mannequin_interface_test'
} else {
  $Status = 'pending_mockup_build_record'
}

$Output = [ordered]@{
  kind = 'francis.fr017.mockup_readiness_gate'
  mode = $Mode
  status = $Status
  measurement_status = $MeasurementStatus
  mockup_status = $MockupStatus
  measurement_path = $ResolvedMeasurementPath
  mockup_path = $ResolvedMockupPath
  using_measurement_template = $UsingMeasurementTemplate
  using_mockup_template = $UsingMockupTemplate
  measurement_parse_ok = $MeasurementParseOk
  upstream_measurement_intake_status = $MeasurementIntakeStatus
  upstream_measurement_intake_exit_code = [int]$MeasurementIntake.exit_code
  upstream_measurement_intake_parse_ok = [bool]$MeasurementIntake.parse_ok
  upstream_measurement_intake_ready = $MeasurementIntakeReady
  mockup_parse_ok = $MockupParseOk
  read_only_contract = $true
  writes_repo = $false
  writes_data = $false
  grants_execution_authority = $false
  grants_mutation_authority = $false
  physical_validation_complete = $false
  mannequin_interface_test_ready = ($Status -eq 'ready_for_mannequin_interface_test')
  mannequin_interface_test_complete = $false
  pilot_testing_cleared = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  required_measurement_fields = $RequiredMeasurementFields
  required_marked_zone_fields = $RequiredMarkedZoneFields
  required_material_fields = $RequiredMaterialFields
  required_constraint_fields = $RequiredConstraintFields
  required_side_check_fields = $RequiredSideCheckFields
  evidence_date_contract = 'Use an ISO 8601 calendar date in YYYY-MM-DD format for evidence.date. Future-dated mockup or measurement evidence is invalid because it cannot be completed evidence.'
  evidence_chronology_contract = 'Mockup evidence.date must be the same as or later than the linked measurement evidence.date. A mockup cannot advance from measurements that were not yet recorded.'
  build_method_contract = 'Mockup evidence.build_method must explicitly state a non-powered soft or semi-rigid cuff mockup. Build-method text that omits non-powered or omits soft/semi-rigid construction is invalid because FR-017 cuffs are not powered joints, frames, armor, or load-bearing structures.'
  record_linkage_contract = 'The mockup build evidence.measurement_record_path must resolve to the same measurement record path passed into this gate. A mockup cannot advance from stale, copied, or unrelated measurement evidence.'
  boolean_value_contract = 'Use unquoted JSON boolean true only when the mockup condition is directly verified. Use false for a verified failure; false blocks progression. Any string value such as yes/no/1/0/"true"/"false" is invalid.'
  measurement_missing_fields = @($MeasurementMissing.ToArray())
  measurement_invalid_fields = @($MeasurementInvalid.ToArray())
  measurement_consistency_violations = @($MeasurementConsistencyViolations.ToArray())
  marked_zone_specificity_violations = @($MarkedZoneSpecificityViolations.ToArray())
  repeatability_blockers = @($RepeatabilityBlockers.ToArray())
  left_right_independence_blockers = @($LeftRightIndependenceBlockers.ToArray())
  measurement_condition_blockers = @($MeasurementConditionBlockers.ToArray())
  landmark_confirmation_blockers = @($LandmarkConfirmationBlockers.ToArray())
  measurement_note_blockers = @($MeasurementNoteBlockers.ToArray())
  safety_blockers = @($SafetyBlockers.ToArray())
  mockup_missing_fields = @($MockupMissing.ToArray())
  mockup_invalid_fields = @($MockupInvalid.ToArray())
  mockup_linkage_violations = @($MockupLinkageViolations.ToArray())
  mockup_chronology_violations = @($MockupChronologyViolations.ToArray())
  mockup_redesign_triggers = @($MockupRedesign.ToArray())
  next_actions = if ($Status -eq 'ready_for_mannequin_interface_test') {
    @(
      'run_non_powered_mannequin_interface_test',
      'record_release_visibility_and_access',
      'record_cable_sleeve_snag_check_before_pilot_static_fit'
    )
  } elseif ($Status -eq 'pending_mockup_build_record') {
    @(
      'build_non_powered_soft_cuff_mockup_from_completed_measurements',
      'complete_FR-017_mockup_build_record',
      'rerun_mockup_readiness_gate'
    )
  } elseif ($Status -eq 'pending_measurement_intake') {
    @(
      'complete_measurement_intake_with_left_right_values',
      'complete_symptom_free_safety_screen',
      'rerun_mockup_readiness_gate'
    )
  } else {
    @(
      'stop_FR-017_progression',
      'correct_failed_measurement_or_mockup_condition',
      'rerun_gate_before_any_mannequin_or_pilot_test'
    )
  }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
